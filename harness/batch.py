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

FROZEN = Path("results/final/FROZEN.txt")  # v1: original scope
FROZEN_V2 = Path("results/v2/FROZEN.txt")  # pivot v0.4: timing and element matching
V2_TYPES = {"timing", "element_matching"}


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
    ap.add_argument("--variants", nargs="+", help="only these variants of the split (default: all of them)")
    a = ap.parse_args()

    batch_id = f"b{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
    catalog = load_catalog()
    variants = [v for v, t in catalog.items() if t["split"] == a.split]
    if a.variants:
        if missing := set(a.variants) - set(variants):
            raise SystemExit(f"not in the {a.split} split: {sorted(missing)}")
        variants = [v for v in variants if v in a.variants]
    if a.split == "holdout":
        for v in variants:  # each variant's holdout waits on the freeze of the agent version it belongs to
            frozen = FROZEN_V2 if catalog[v]["type"] in V2_TYPES else FROZEN
            if not frozen.exists():
                raise SystemExit(f"holdout {v} needs a frozen agent: {frozen} not found")
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
