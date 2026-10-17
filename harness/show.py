"""Print the last N heals from logs/attempts.jsonl in readable form.
Usage: uv run python -m harness.show [--last 1] [--variant sc_03]
"""
import argparse
import json

from harness.heal import ATTEMPTS


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--last", type=int, default=1, help="number of heals to show")
    ap.add_argument("--variant")
    a = ap.parse_args()
    rows = [json.loads(l) for l in ATTEMPTS.read_text().splitlines() if l.strip()]
    if a.variant:
        rows = [r for r in rows if r["variant"] == a.variant]
    heals = list(dict.fromkeys(r["heal_id"] for r in rows))[-a.last:]
    for hid in heals:
        attempts = [r for r in rows if r["heal_id"] == hid]
        f = attempts[-1]
        print(f"=== {f['variant']} ({f['failure_type']}, split {f['split']}) on {f['case']} | bundle runs/{hid}/")
        print(f"first failure: step {f['first_failing_step']}: {f['first_error']}")
        print(f"truth: cause {f['truth_cause']}, expected {f['expected_decision']} | "
              f"FINAL: {f['final_decision']} {'(matches)' if f['final_decision'] == f['expected_decision'] else '(MISMATCH)'}")
        for r in attempts:
            out = r.get("agent_output") or {}
            print(f"\n-- attempt {r['attempt']}: {r['decision']} | cause {out.get('cause_category')}/{out.get('cause_detail')} "
                  f"conf {out.get('confidence')} | {r['tool_calls']} tool calls | ${r['cost_usd']:.4f}")
            if r.get("patch_applied"):
                print(f"   rerun: script_passed={r['script_passed']} oracle_passed={r['oracle_passed']} "
                      f"diff_lines={r['diff_lines']} rerun=runs/{r['rerun_run_id']}/")
            if r.get("error"):
                print(f"   error: {r['error']}")
            for e in out.get("evidence", []):
                print(f"   evidence: {e}")
            if out.get("patch"):
                print("   patch:\n" + "\n".join("     " + l for l in out["patch"].splitlines()))
            if out.get("reasoning"):
                print(f"   reasoning: {out['reasoning']}")
        print()


if __name__ == "__main__":
    main()
