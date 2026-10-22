"""Heal one injected failure end to end: write logs/heals/<heal_id>.json and append one line per
attempt to logs/attempts.jsonl.

The harness runs the script with the variant, hands only the bundle and script path to the agent,
and supplies the judge (rerun with the same variant + oracle + policy). Ground truth from the
catalog is joined onto the attempt records only after the agent has finished.
Usage: HEAL_MODEL=claude-haiku-5-5 uv run python -m harness.heal --variant sc_03
"""
import argparse
import json
import subprocess
from pathlib import Path

from dotenv import load_dotenv

import policy
from agent.heal import AGENT_VERSION, heal, model_from_env
from failures.injectors import load_catalog
from harness.run import RUNS, SCRIPTS, run, variant_case

ATTEMPTS = Path("logs/attempts.jsonl")  # index: one line per attempt, linking to its heal file
HEALS = Path("logs/heals")  # one <heal_id>.json per heal, with the full transcript
load_dotenv()  # ANTHROPIC_API_KEY; an inline HEAL_MODEL=... wins over .env


def split_variant(variant: str, split: str) -> dict:
    truth = load_catalog()[variant]
    if truth["split"] != split:
        raise SystemExit(f"{variant} is in the {truth['split']} split, not {split}; holdout runs only via the batch")
    return truth


def heal_case(variant: str, case_index: int = 0, batch_id: str | None = None, split: str = "dev",
              headed: bool = False, slowmo: float = 0) -> list[dict]:
    truth = split_variant(variant, split)
    model = model_from_env()
    script = truth["script"]
    script_path = Path("scripts") / f"{script}.py"
    cases = SCRIPTS[script][0]
    case = variant_case(script, variant) or cases[case_index % len(cases)]

    first = run(script, variant, case, headed=headed, slowmo=slowmo)
    if first.passed:  # injector didn't break the run; nothing to heal
        records = [{"attempt": 0, "agent_version": AGENT_VERSION, "model": model, "agent_output": None,
                    "decision": "no_failure", "final_decision": "no_failure", "patch_applied": False,
                    "patch_discarded": False, "diff_lines": 0, "script_passed": True, "oracle_passed": True,
                    "tool_calls": 0, "model_calls": 0, "input_tokens": 0, "output_tokens": 0,
                    "cache_read_tokens": 0, "cache_write_tokens": 0, "cost_usd": 0.0, "wall_seconds": 0.0,
                    "transcript": []}]
    else:
        original = script_path.read_text()

        def judge(sandbox, diag, diff_lines, touched):
            try:
                r = run(script, variant, case, script_path=sandbox, headed=headed, slowmo=slowmo)
            except (RuntimeError, subprocess.TimeoutExpired) as e:  # patched script crashed the child or hung
                return {"script_passed": False, "oracle_passed": False, "rerun_run_id": None,
                        "bundle_dir": None, "error": f"{type(e).__name__}: {str(e)[:500]}", "decision": "escalate"}
            return {"script_passed": r.script_passed, "oracle_passed": r.passed, "rerun_run_id": r.run_id,
                    "bundle_dir": r.bundle_dir, "error": r.error,
                    "decision": policy.decide(diag, diff_lines, touched, original, r.script_passed, r.passed,
                                              first_error=first.error)}

        records = heal(Path(first.bundle_dir), script_path, judge, model)

    # Joined only now, after the agent is done.
    joined = {"run_id": first.run_id, "heal_id": first.run_id, "batch_id": batch_id, "script": script, "case": " ".join(case),
              "failure_type": truth["type"], "variant": variant, "split": truth["split"],
              "truth_cause": truth["truth_cause"], "expected_decision": truth["expected_decision"],
              "first_failing_step": first.failing_step, "first_error": first.error,
              "injector_unmatched": first.injector_unmatched}
    out = []
    for i, rec in enumerate(records):
        # Every rerun bad fix counts, including ones that failed before decide, so it is tagged here.
        patch = (rec.get("agent_output") or {}).get("patch")
        out.append({**joined, **rec, "final_decision": rec.get("final_decision"), "is_final": i == len(records) - 1,
                    "bad_fix_type": policy.bad_fix(patch, first.error) if rec.get("patch_applied") else None})
    diff = RUNS / first.run_id / "heal.diff"  # written by the agent loop on auto_apply
    log = write_heal_log(joined, out, diff if out[-1]["final_decision"] == "auto_apply" and diff.exists() else None)
    ATTEMPTS.parent.mkdir(exist_ok=True)
    with ATTEMPTS.open("a") as f:
        for rec in out:  # the index line: everything but the transcript, which lives in the heal file
            f.write(json.dumps({**{k: v for k, v in rec.items() if k != "transcript"}, "heal_log": str(log)},
                               default=str) + "\n")
    return out


def write_heal_log(joined: dict, attempts: list[dict], approved_diff: Path | None) -> Path:
    """One file per heal with every attempt in full, transcripts included. Kept under logs/, which the
    agent's guard denies, because it holds the truth labels."""
    path = HEALS / f"{joined['heal_id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({**joined, "final_decision": attempts[-1]["final_decision"],
                                "attempts_used": len(attempts),
                                "cost_usd": round(sum(a["cost_usd"] for a in attempts), 6),
                                "approved_diff": str(approved_diff) if approved_diff else None,
                                "attempts": attempts}, indent=1, default=str))
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True)
    ap.add_argument("--case", type=int, default=0, help="index into the script's test cases")
    # scratch = your own experiments; batch and scorecard only count dev and holdout
    ap.add_argument("--split", choices=["dev", "scratch"], default="dev")
    ap.add_argument("--headed", action="store_true", help="show the browser (demo)")
    ap.add_argument("--slowmo", type=float, default=0, help="ms between Playwright actions (demo)")
    a = ap.parse_args()
    for rec in heal_case(a.variant, a.case, split=a.split, headed=a.headed, slowmo=a.slowmo):
        print(json.dumps({k: v for k, v in rec.items() if k not in ("calls", "transcript")}))


if __name__ == "__main__":
    main()
