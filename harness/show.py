"""Print the last N heals from logs/attempts.jsonl in readable form.
Usage: uv run python -m harness.show [--last 1] [--variant sc_03] [--transcript]
"""
import argparse
import json
from pathlib import Path

from harness.heal import ATTEMPTS


def _short(text: str, n: int = 120) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n] + " ..."


def print_transcript(attempt: dict) -> None:
    """The agent's calls from one attempt's transcript, one short line each."""
    print("   transcript:")
    for item in attempt.get("transcript", []):
        if item["kind"] == "assistant":
            for b in item["blocks"]:
                if b["type"] == "text" and b["text"].strip():
                    print(f"     agent says: {_short(b['text'].strip().splitlines()[0])}")
                elif b["type"] == "tool_use" and b["name"] == "submit_diagnosis":
                    print("     agent calls submit_diagnosis (shown above)")
                elif b["type"] == "tool_use":
                    print(f"     agent calls {b['name']}({json.dumps(b['input']) if b['input'] else ''})")
        elif item["kind"] == "tool_results":
            for r in item["results"]:
                print(f"       -> {'ERROR ' if r['is_error'] else ''}{_short(r['content'])}")
        elif item["kind"] == "nudge":
            print(f"     harness: {item['text']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--last", type=int, default=1, help="number of heals to show")
    ap.add_argument("--variant")
    ap.add_argument("--transcript", action="store_true", help="also print each tool call from the heal file")
    a = ap.parse_args()
    rows = [json.loads(l) for l in ATTEMPTS.read_text().splitlines() if l.strip()]
    if a.variant:
        rows = [r for r in rows if r["variant"] == a.variant]
    heals = list(dict.fromkeys(r["heal_id"] for r in rows))[-a.last:]
    for hid in heals:
        attempts = [r for r in rows if r["heal_id"] == hid]
        f = attempts[-1]
        print(f"=== {f['variant']} ({f['failure_type']}, split {f['split']}) on {f['case']} | bundle runs/{hid}/")
        heal_log = Path(f["heal_log"]) if f.get("heal_log") else None
        if heal_log:
            print(f"full log: {heal_log}")
        print(f"first failure: step {f['first_failing_step']}: {f['first_error']}")
        print(f"truth: cause {f['truth_cause']}, expected {f['expected_decision']} | "
              f"FINAL: {f['final_decision']} {'(matches)' if f['final_decision'] == f['expected_decision'] else '(MISMATCH)'}")
        full = json.loads(heal_log.read_text())["attempts"] if a.transcript and heal_log else []
        for i, r in enumerate(attempts):
            out = r.get("agent_output") or {}
            print(f"\n-- attempt {r['attempt']}: {r['decision']} | cause {out.get('cause_category')}/{out.get('cause_detail')} "
                  f"conf {out.get('confidence')} | {r['tool_calls']} tool calls | ${r['cost_usd']:.4f}")
            if r.get("patch_applied"):
                print(f"   rerun: script_passed={r['script_passed']} oracle_passed={r['oracle_passed']} "
                      f"diff_lines={r['diff_lines']} rerun=runs/{r['rerun_run_id']}/")
            if r.get("bad_fix_type"):
                print(f"   BAD FIX: {r['bad_fix_type']} "
                      f"({'rejected by policy after the sandbox rerun, not kept' if r['decision'] == 'rejected_bad_fix' else 'sandbox rerun failed'})")
            if r.get("error"):
                print(f"   error: {r['error']}")
            for e in out.get("evidence", []):
                print(f"   evidence: {e}")
            if out.get("patch"):
                print("   patch:\n" + "\n".join("     " + l for l in out["patch"].splitlines()))
            if out.get("reasoning"):
                print(f"   reasoning: {out['reasoning']}")
            if a.transcript and not heal_log:
                print("   (no transcript: logged before per-heal files existed)")
            elif full:
                print_transcript(full[i])
        print()


if __name__ == "__main__":
    main()
