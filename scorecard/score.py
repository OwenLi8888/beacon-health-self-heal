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
           f"| Tries per heal (mean attempts over heals) | {f'{tries:.2f} ({len(healed)} heals)' if tries is not None else 'n/a (0 heals)'} |",
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


FLAKY = {"timing": "tm", "element_matching": "em"}
BAD_FIXES = ("fixed_sleep", "positional_pick", "wrong_patient")


def bad_fix_types(r: dict) -> set[str]:
    """Bad-fix types of one attempt. wrong_patient = a patched element-matching rerun that finished
    but failed the oracle (the script read some other chart)."""
    types = {r["bad_fix_type"]} if r.get("bad_fix_type") else set()
    if (r["failure_type"] == "element_matching" and r["patch_applied"] and r["script_passed"]
            and not r["oracle_passed"]):
        types.add("wrong_patient")
    return types


def flaky_section(rows: list[dict]) -> list[str]:
    """Pivot v0.4 (B6): timing and element matching, dev and holdout side by side, plus bad fixes."""
    rows = [r for r in rows if r["failure_type"] in FLAKY]
    cases = defaultdict(list)
    for r in rows:
        cases[r["heal_id"]].append(r)
    finals = [sorted(a, key=lambda r: r["attempt"])[-1] for a in cases.values()]
    finals = [f for f in finals if f["final_decision"] != "no_failure"]
    cols = [(t, s) for t in FLAKY for s in ("dev", "holdout")]

    def cell(t, s, metric):
        fs = [f for f in finals if f["failure_type"] == t and f["split"] == s]
        if not fs:
            return "not run"
        heals = [f for f in fs if f["final_decision"] == "auto_apply" and f["oracle_passed"]]
        atts = [r for f in fs for r in cases[f["heal_id"]]]
        if metric == "heal":
            return rate(len(heals), len(fs))
        if metric == "decision":
            return rate(sum(f["final_decision"] == f["expected_decision"] for f in fs), len(fs))
        if metric == "cause":
            return rate(sum(cause_correct(f["truth_cause"], f["agent_output"]) for f in fs), len(fs))
        if metric == "detail":
            return ", ".join(f"{d} {n}" for d, n in sorted(Counter(
                (f["agent_output"] or {}).get("cause_detail") for f in fs).items(), key=str))
        if metric == "tries":
            return f"{sum(f['attempt'] for f in heals) / len(heals):.2f} ({len(heals)} heals)" if heals else "n/a (0 heals)"
        if metric == "attempts":
            return str(len(atts))
        return f"${sum(r['cost_usd'] for r in atts):.4f}"

    metrics = [("heal", "Heal rate (auto-applied, oracle pass / cases)"),
               ("decision", "Final decision = expected / cases"),
               ("cause", "Cause correct (script / cases)"),
               ("detail", "cause_detail chosen (schema has no timing/matching value)"),
               ("tries", "Tries per heal"), ("attempts", "Attempts"), ("cost", "Cost")]
    out = ["## Timing and element matching (16% of Beacon failures)", "",
           "| Metric | " + " | ".join(f"{FLAKY[t]} {s}" for t, s in cols) + " |", "|---|" + "---|" * len(cols)]
    out += [f"| {label} | " + " | ".join(cell(t, s, m) for t, s in cols) + " |" for m, label in metrics]

    attempts = [r for r in rows if r["decision"] != "no_failure"]
    out += ["", "Bad-fix attempts by type (every attempt, applied or not; applied must be 0):", "",
            "| Type | Rejected | Applied | Total |", "|---|---|---|---|"]
    for t in BAD_FIXES:
        hit = [r for r in attempts if t in bad_fix_types(r)]
        applied = sum(r["decision"] == "auto_apply" for r in hit)
        out.append(f"| {t} | {len(hit) - applied} | {applied} | {len(hit)} of {len(attempts)} attempts |")
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
    ap.add_argument("--log", type=Path, default=ATTEMPTS, help="attempt log; results/final/attempts.jsonl is the committed copy")
    ap.add_argument("--v1-log", type=Path, help="also add a 'v1: original scope' section from this log (read only)")
    a = ap.parse_args()
    rows = [json.loads(l) for l in a.log.read_text().splitlines() if l.strip()]
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
    if any(r["failure_type"] in FLAKY for r in rows):
        lines += flaky_section(rows)
    for s in sections.values():
        lines += s
    if a.v1_log:
        v1 = [json.loads(l) for l in a.v1_log.read_text().splitlines() if l.strip()]
        lines += [f"# v1: original scope (from {a.v1_log})", ""]
        for split in ("dev", "holdout"):
            lines += [l.replace(f"## {split}", f"## v1 {split}", 1) for l in section(split, [r for r in v1 if r["split"] == split])]
    out = a.out or Path("results") / a.batch[0] / "scorecard.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))
    print("\n".join(lines))
    print(f"\nwritten: {out}")


if __name__ == "__main__":
    main()
