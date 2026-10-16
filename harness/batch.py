"""Batch: every variant in a split x N repeats, DB reset before every run (harness.run does it).

Stops before the next case once this batch's logged spend reaches --budget-usd, so a batch can
overshoot by at most one case. Only the dev split is allowed until the agent is frozen.
Usage: HEAL_MODEL=claude-sonnet-5-5 uv run python -m harness.batch --split dev --repeats 3 --budget-usd 5
"""
import argparse
import json
import secrets
from datetime import datetime
from pathlib import Path

from failures.injectors import load_catalog
from harness.heal import ATTEMPTS, heal_case

FROZEN = Path("results/final/FROZEN.txt")


def spent(batch_id: str) -> float:
    if not ATTEMPTS.exists():
        return 0.0
    rows = (json.loads(line) for line in ATTEMPTS.read_text().splitlines() if line.strip())
    return sum(r["cost_usd"] for r in rows if r.get("batch_id") == batch_id)


def main() -> None:
    ap = argparse.ArgumentParser()
    # Holdout runs once, after the agent is frozen (results/final/FROZEN.txt must exist).
    ap.add_argument("--split", choices=["dev", "holdout"], required=True)
    ap.add_argument("--repeats", type=int, required=True)
    ap.add_argument("--budget-usd", type=float, required=True)
    a = ap.parse_args()
    if a.split == "holdout" and not FROZEN.exists():
        raise SystemExit(f"holdout needs a frozen agent: {FROZEN} not found")

    batch_id = f"b{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
    variants = [v for v, t in load_catalog().items() if t["split"] == a.split]
    print(f"batch {batch_id}: {len(variants)} variants x {a.repeats} repeats, budget ${a.budget_usd}", flush=True)
    for rep in range(a.repeats):
        for v in variants:
            if (s := spent(batch_id)) >= a.budget_usd:
                print(f"budget reached (${s:.4f} >= ${a.budget_usd}); stopping", flush=True)
                print(batch_id)
                return
            final = heal_case(v, case_index=rep, batch_id=batch_id, split=a.split)[-1]
            print(json.dumps({"variant": v, "repeat": rep + 1, "final_decision": final["final_decision"],
                              "attempts": final["attempt"], "spent_usd": round(spent(batch_id), 4)}), flush=True)
    print(batch_id)


if __name__ == "__main__":
    main()
