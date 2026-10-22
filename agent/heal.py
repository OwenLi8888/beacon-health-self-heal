"""Heal agent: diagnose a failed run from its bundle, patch a sandbox copy, hand it to the judge.

Input is the bundle dir and the script path only. The agent never learns the injected variant, its
labels, the oracle or the policy: `judge` is a harness callback that reruns the sandbox copy with the
same failure, checks the outcome, applies the policy and returns only the verdict.
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Callable

import anthropic
from pydantic import ValidationError

from agent import patch as patching
from agent.guard import safe_read
from agent.schema import Diagnosis
from agent.tools import TOOLS, Toolbox

AGENT_VERSION = "v3"
MAX_ATTEMPTS = 3
MAX_TOOL_CALLS = 8
MAX_MODEL_CALLS = MAX_TOOL_CALLS + 2  # room for nudges when the model answers in text
SYSTEM = [{"type": "text", "text": Path(__file__).with_name("prompt.md").read_text(),
           "cache_control": {"type": "ephemeral"}}]
# USD per million tokens: input, output, cache read, cache write (5 min). Prompts here stay under
# Haiku 5.5's 100K long-prompt tier.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20, 2.50),
}
FAILED = {"no_submit", "patch_failed", "rerun_failed"}  # attempt outcomes that lead to a retry
RESULT_CAP = 3000  # chars of each tool result kept in the transcript

# judge(sandbox_script, diagnosis, diff_lines, touched_lines) ->
#   {"script_passed", "oracle_passed", "decision", "rerun_run_id", "bundle_dir", "error"}
Judge = Callable[[Path, Diagnosis, int, list[int]], dict]


def model_from_env() -> str:
    model = os.environ.get("HEAL_MODEL")
    if not model:
        raise RuntimeError("HEAL_MODEL is not set")
    if model not in PRICES:
        raise RuntimeError(f"no price for model {model!r}; add it to agent.heal.PRICES")
    return model


def _cost(model: str, u) -> dict:
    p_in, p_out, p_read, p_write = PRICES[model]
    row = {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
           "cache_read_tokens": u.cache_read_input_tokens or 0,
           "cache_write_tokens": u.cache_creation_input_tokens or 0}
    row["cost_usd"] = round((row["input_tokens"] * p_in + row["output_tokens"] * p_out
                             + row["cache_read_tokens"] * p_read + row["cache_write_tokens"] * p_write) / 1e6, 6)
    return row


def _brief(bundle_dir: Path, feedback: str | None) -> str:
    err = json.loads(safe_read(bundle_dir / "error.json", [bundle_dir]))
    parts = [f"The script failed.\nFailing step: {err.get('failing_step')}\n"
             f"Error: {err['error_type']}: {err['message']}"]
    if err.get("traceback"):
        parts.append(f"Traceback:\n{err['traceback'][-4000:]}")
    if feedback:
        parts.append(f"Previous attempt:\n{feedback}")
    parts.append("Investigate with the tools, then call submit_diagnosis.")
    return "\n\n".join(parts)


def _block(b) -> dict:
    """An assistant content block as plain JSON for the transcript."""
    if b.type == "text":
        return {"type": "text", "text": b.text}
    if b.type == "tool_use":
        return {"type": "tool_use", "name": b.name, "input": b.input}
    return {"type": b.type}


def _result(r: dict) -> dict:
    """A tool result as plain JSON for the transcript: images by kind only, long text capped."""
    content = r["content"]
    if isinstance(content, list):
        content = "\n".join("[image]" if c.get("type") == "image" else c.get("text", f"[{c.get('type')}]")
                            for c in content)
    if len(content) > RESULT_CAP:
        content = content[:RESULT_CAP] + " [truncated]"
    return {"is_error": r.get("is_error", False), "content": content}


def _diagnose(client, model: str, bundle_dir: Path, sandbox: Path, feedback: str | None) -> tuple[dict, Diagnosis | None]:
    """One attempt's tool loop. Returns usage totals and the diagnosis (None if never submitted).

    `transcript` is a record of the loop for the heal log. It is never sent back to the model.
    """
    box = Toolbox(bundle_dir, sandbox)
    messages = [{"role": "user", "content": _brief(bundle_dir, feedback)}]
    transcript = [{"kind": "brief", "text": messages[0]["content"]}]
    calls, tool_calls = [], 0
    for _ in range(MAX_MODEL_CALLS):
        try:
            resp = client.messages.create(model=model, max_tokens=16000, system=SYSTEM, tools=TOOLS, messages=messages)
        except anthropic.APIError as e:  # after the SDK's own retries; keep what was already spent
            return {**_totals(calls, tool_calls, transcript), "api_error": f"{type(e).__name__}: {e}"}, None
        calls.append(_cost(model, resp.usage))
        print(json.dumps({"event": "model_call", "model": model, **calls[-1]}), file=sys.stderr, flush=True)
        messages.append({"role": "assistant", "content": resp.content})
        transcript.append({"kind": "assistant", "blocks": [_block(b) for b in resp.content], "usage": calls[-1]})
        uses = [b for b in resp.content if b.type == "tool_use"]
        if not uses:
            messages.append({"role": "user", "content": "Call submit_diagnosis to finish this attempt."})
            transcript.append({"kind": "nudge", "text": messages[-1]["content"]})
            continue
        results = []
        for use in uses:
            if use.name != "submit_diagnosis" and tool_calls >= MAX_TOOL_CALLS - 1:
                # The last call is reserved for submit_diagnosis, even when calls arrive in parallel.
                results.append({"type": "tool_result", "tool_use_id": use.id, "is_error": True,
                                "content": "Tool budget used up: only submit_diagnosis is allowed now."})
                continue
            tool_calls += 1
            if use.name == "submit_diagnosis":
                try:
                    diag = Diagnosis(**use.input)
                    if results:  # results of calls made alongside the submit in the same turn
                        transcript.append({"kind": "tool_results", "results": [_result(r) for r in results]})
                    return _totals(calls, tool_calls, transcript), diag
                except ValidationError as e:
                    results.append({"type": "tool_result", "tool_use_id": use.id, "is_error": True,
                                    "content": f"Invalid diagnosis: {e}"})
                    continue
            try:
                content = box.run(use.name, use.input)
                results.append({"type": "tool_result", "tool_use_id": use.id, "content": content})
            except Exception as e:  # unknown tool, denied path, bad args: tell the model, don't crash
                results.append({"type": "tool_result", "tool_use_id": use.id, "is_error": True,
                                "content": f"{type(e).__name__}: {e}"})
        transcript.append({"kind": "tool_results", "results": [_result(r) for r in results]})
        if tool_calls >= MAX_TOOL_CALLS:
            break
        if tool_calls >= MAX_TOOL_CALLS - 1:
            results.append({"type": "text", "text": "One tool call left: call submit_diagnosis now."})
            transcript.append({"kind": "nudge", "text": results[-1]["text"]})
        messages.append({"role": "user", "content": results})
    return _totals(calls, tool_calls, transcript), None


def _totals(calls: list[dict], tool_calls: int, transcript: list[dict]) -> dict:
    keys = ["input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"]
    out = {k: sum(c[k] for c in calls) for k in keys}
    out.update(cost_usd=round(sum(c["cost_usd"] for c in calls), 6), tool_calls=tool_calls,
               model_calls=len(calls), calls=calls, transcript=transcript)
    return out


def heal(bundle_dir: Path, script_path: Path, judge: Judge, model: str) -> list[dict]:
    """Run up to MAX_ATTEMPTS attempts. Returns one record per attempt; the last has final_decision."""
    client = anthropic.Anthropic()
    bundle_dir, script_path = Path(bundle_dir), Path(script_path)
    original = safe_read(script_path, [script_path.parent])
    records, feedback, bundle = [], None, bundle_dir
    for n in range(1, MAX_ATTEMPTS + 1):
        start = time.monotonic()
        sandbox = bundle_dir / "sandbox" / f"a{n}" / script_path.name
        sandbox.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(script_path, sandbox)
        usage, diag = _diagnose(client, model, bundle, sandbox, feedback)
        rec = {"attempt": n, "agent_version": AGENT_VERSION, "model": model, "bundle_path": str(bundle),
               "agent_output": diag.model_dump() if diag else None, "patch_applied": False,
               "patch_discarded": False, "diff_lines": 0, "script_passed": None, "oracle_passed": None,
               "rerun_run_id": None, "error": None, **usage}
        records.append(rec)

        if rec.get("api_error"):
            rec.update(decision="api_error", error=rec["api_error"])
        elif diag is None:
            rec["decision"] = "no_submit"
            feedback = f"You used all {MAX_TOOL_CALLS} tool calls without calling submit_diagnosis."
        elif diag.cause_category != "script":
            rec["patch_discarded"] = diag.patch is not None  # F7: never apply a patch for a non-script cause
            rec["decision"] = "reported" if diag.cause_category in ("site", "infra") else "escalate"
        elif not diag.patch:
            rec["decision"] = "escalate"
        else:
            try:
                patched = patching.apply(original, diag.patch)
            except patching.PatchError as e:
                rec.update(decision="patch_failed", error=str(e))
                feedback = f"Your patch could not be applied: {e}\nPatch was:\n{diag.patch}"
            else:
                sandbox.write_text(patched)
                rec["diff_lines"], touched = patching.changed_lines(original, patched)
                rec["patch_applied"] = True
                verdict = judge(sandbox, diag, rec["diff_lines"], touched)
                rec.update(script_passed=verdict["script_passed"], oracle_passed=verdict["oracle_passed"],
                           rerun_run_id=verdict["rerun_run_id"], error=verdict["error"])
                if verdict["oracle_passed"]:
                    rec["decision"] = verdict["decision"]
                    if rec["decision"] == "auto_apply":  # approved; the original script is never overwritten
                        (bundle_dir / "heal.diff").write_text(patching.unified(original, patched, script_path.name))
                else:
                    rec["decision"] = "rerun_failed"
                    feedback = (f"Your patch was applied to a copy of the script and rerun, and the run still "
                                f"failed: {verdict['error']}\nPatch was:\n{diag.patch}\n"
                                f"The bundle and tools now show the rerun's failure.")
                    # An outcome-check failure bundle has no DOM or screenshot; keep the last one that does.
                    if verdict["bundle_dir"] and (Path(verdict["bundle_dir"]) / "dom.html").exists():
                        bundle = Path(verdict["bundle_dir"])
        rec["wall_seconds"] = round(time.monotonic() - start, 1)
        if rec["decision"] not in FAILED:
            break
    last = records[-1]
    last["final_decision"] = "gave_up" if last["decision"] in FAILED | {"api_error"} else last["decision"]
    return records
