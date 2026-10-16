"""Scorecard from logs/attempts.jsonl alone. Writes results/<batch>/scorecard.md and prints it.
Usage: uv run python -m scorecard.score --batch <batch_id>
"""
import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ATTEMPTS = Path("logs/attempts.jsonl")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def rate(k: int, n: int) -> str:
    if n == 0:
        return "n/a (0 of 0)"
    lo, hi = wilson(k, n)
    return f"{100 * k / n:.0f}% ({k} of {n}; 95% CI {100 * lo:.0f}% to {100 * hi:.0f}%)"


def cause_correct(truth: str, out: dict | None) -> bool:
    if not out:
        return False
    return out["cause_category"] == "script" if truth == "script" else out["cause_category"] in ("site", "infra")


def section(split: str, rows: list[dict]) -> list[str]:
    cases = defaultdict(list)
    for r in rows:
        cases[r["heal_id"]].append(r)
    finals = [sorted(a, key=lambda r: r["attempt"])[-1] for a in cases.values()]
    no_failure = [f for f in finals if f["final_decision"] == "no_failure"]
    finals = [f for f in finals if f["final_decision"] != "no_failure"]
    attempts = [r for r in rows if r["decision"] != "no_failure"]

    healable = [f for f in finals if f["truth_cause"] == "script" and f["expected_decision"] == "auto_apply"]
    healed = [f for f in healable if f["final_decision"] == "auto_apply" and f["oracle_passed"]]
    patched = [r for r in attempts if r["patch_applied"]]
    wrong = [r for r in patched if r["script_passed"] and not r["oracle_passed"]]
    non_script = [f for f in finals if f["truth_cause"] != "script"]
    ns_patched = [f for f in non_script if any(r["patch_applied"] for r in cases[f["heal_id"]])]
    ns_discarded = sum(r["patch_discarded"] for f in non_script for r in cases[f["heal_id"]])
    correct = [f for f in finals if f["final_decision"] == f["expected_decision"]]
    diag_ok = [f for f in finals if cause_correct(f["truth_cause"], f["agent_output"])]
    detail_ok = [f for f in finals if f["agent_output"] and f["agent_output"]["cause_detail"] == f["failure_type"]]
    cost = sum(r["cost_usd"] for r in rows)
    tries = sum(f["attempt"] for f in healed) / len(healed) if healed else None
    unmatched = sum(bool(f.get("injector_unmatched")) for f in finals + no_failure)

    out = [f"## {split}", "",
           f"Cases: {len(finals)} failures healed or handled, {len(no_failure)} where the injected run did not fail, "
           f"{unmatched} with an injector that matched nothing. Attempts: {len(attempts)}.", "",
           "| Metric | Value |", "|---|---|",
           f"| Heal rate (auto-applied, oracle pass / heal-able) | {rate(len(healed), len(healable))} |",
           f"| **Wrong-fix rate, caught in sandbox** (script pass, oracle fail / patched reruns) | {rate(len(wrong), len(patched))} |",
           f"| Wrong fixes auto-applied (0 by construction: policy needs an oracle pass) | "
           f"{sum(f['final_decision'] == 'auto_apply' and not f['oracle_passed'] for f in finals)} |",
           f"| Non-script patch rate (cases with a patch applied / non-script cases) | {rate(len(ns_patched), len(non_script))} |",
           f"| Escalation correctness (final decision = expected / cases) | {rate(len(correct), len(finals))} |",
           f"| Cause correct (script vs site/infra / cases) | {rate(len(diag_ok), len(finals))} |",
           f"| Diagnosis accuracy (cause_detail = failure type / cases) | {rate(len(detail_ok), len(finals))} |",
           f"| Tries per heal (mean attempts, {len(healed)} heals) | {f'{tries:.2f}' if tries is not None else 'n/a'} |",
           f"| Cost per heal | {f'${cost / len(healed):.4f} (${cost:.4f} / {len(healed)})' if healed else f'n/a (${cost:.4f} spent, 0 heals)'} |",
           f"| Total cost | ${cost:.4f} |",
           f"| Non-script patches discarded by the harness | {ns_discarded} |", ""]

    matrix = Counter((f["expected_decision"], f["final_decision"]) for f in finals)
    finals_seen = sorted({d for _, d in matrix})
    out += ["Decision matrix (rows expected, columns final). `gave_up` = 3 failed attempts, handed to a human; "
            "it never matches an expected decision.", "",
            "| expected \\ final | " + " | ".join(finals_seen) + " |",
            "|---|" + "---|" * len(finals_seen)]
    for exp in sorted({e for e, _ in matrix}):
        out.append(f"| {exp} | " + " | ".join(str(matrix[(exp, d)]) for d in finals_seen) + " |")

    out += ["", "By variant:", "", "| Variant | Truth | Expected | Cases | Final decisions | Attempts | Cost |",
            "|---|---|---|---|---|---|---|"]
    by_variant = defaultdict(list)
    for f in finals:
        by_variant[f["variant"]].append(f)
    for v, fs in sorted(by_variant.items()):
        decisions = ", ".join(f"{d} {n}" for d, n in sorted(Counter(f["final_decision"] for f in fs).items()))
        v_cost = sum(r["cost_usd"] for f in fs for r in cases[f["heal_id"]])
        out.append(f"| {v} | {fs[0]['truth_cause']} | {fs[0]['expected_decision']} | {len(fs)} | {decisions} | "
                   f"{sum(f['attempt'] for f in fs)} | ${v_cost:.4f} |")
    return out + [""]


def metric_rows(lines: list[str]) -> list[tuple[str, str]]:
    """(metric, value) pairs from a section's metric table."""
    start = lines.index("| Metric | Value |") + 2
    end = lines.index("", start)
    return [tuple(c.strip() for c in l.strip("|").split(" | ", 1)) for l in lines[start:end]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True, nargs="+", help="one or more batch ids, e.g. a dev and a holdout batch")
    ap.add_argument("--out", type=Path, help="default: results/<batch>/scorecard.md")
    a = ap.parse_args()
    rows = [json.loads(l) for l in ATTEMPTS.read_text().splitlines() if l.strip()]
    rows = [r for r in rows if r.get("batch_id") in a.batch]
    if not rows:
        raise SystemExit(f"no attempts logged for batch {a.batch}")
    models = sorted({r["model"] for r in rows})
    versions = sorted({r["agent_version"] for r in rows})
    lines = [f"# Scorecard: {', '.join(a.batch)}", "",
             f"Agent {', '.join(versions)}, model {', '.join(models)}. Generated from logs/attempts.jsonl only.", ""]
    sections = {}
    for split in ("dev", "holdout"):
        split_rows = [r for r in rows if r["split"] == split]
        sections[split] = section(split, split_rows) if split_rows else [f"## {split}", "", "Not run.", ""]
    if all("| Metric | Value |" in s for s in sections.values()):
        dev, hold = metric_rows(sections["dev"]), metric_rows(sections["holdout"])
        lines += ["## Dev vs holdout", "", "| Metric | Dev | Holdout |", "|---|---|---|"]
        lines += [f"| {m} | {d} | {h} |" for (m, d), (_, h) in zip(dev, hold)] + [""]
    for s in sections.values():
        lines += s
    out = a.out or Path("results") / a.batch[0] / "scorecard.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))
    print("\n".join(lines))
    print(f"\nwritten: {out}")


if __name__ == "__main__":
    main()
