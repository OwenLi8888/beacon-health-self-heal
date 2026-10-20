"""Block 1 check: every catalog variant breaks its script at the intended step on a clean DB,
and the same script passes again with the variant off. Exits non-zero on any mismatch.
Usage: uv run python -m harness.verify_injectors
"""
import sys
from pathlib import Path

from failures.injectors import load_catalog
from harness.bundle import DOM_CAP
from harness.run import SCRIPTS, run, variant_case

OUT = Path("results/injectors/verify.md")
BUNDLE_FILES = ("error.json", "screenshot.png", "dom.html", "dom_full.html")


def mark(passed: bool) -> str:
    return "pass" if passed else "FAIL"


def main() -> None:
    rows, all_ok = [], True
    cases = {}  # case -> its last clean run
    for vid, v in load_catalog().items():
        case = variant_case(v["script"], vid) or SCRIPTS[v["script"]][0][0]
        before = cases.get(case) or run(v["script"], case=case)
        on = run(v["script"], variant=vid, case=case)
        after = cases[case] = run(v["script"], case=case)
        bundle = Path(on.bundle_dir) if on.bundle_dir else None
        complete = bool(bundle) and all((bundle / f).exists() for f in BUNDLE_FILES)
        dom_kb = (bundle / "dom.html").stat().st_size / 1000 if complete else 0
        ok = (before.passed and not on.passed and not on.injector_unmatched and complete
              and on.failing_step == v["breaks_step"] and dom_kb * 1000 <= DOM_CAP and after.passed)
        all_ok &= ok
        rows.append(f"| {vid} | {v['type']} | {v['split']} | {mark(before.passed)} | {mark(on.passed)} "
                    f"| {on.failing_step} | {v['breaks_step']} | {mark(after.passed)} | {dom_kb:.1f} "
                    f"| {on.error or ''} | {'ok' if ok else 'MISMATCH'} |")
    table = "\n".join([
        "| Variant | Type | Split | Off (before) | On | Failing step | Expected step | Off (after) "
        "| dom.html KB | Error | Result |",
        "|---|---|---|---|---|---|---|---|---|---|---|", *rows])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("# Injector verification (read_a1c; Rosa Delgado unless the variant pins a `patient`; "
                   "DB reset before every run)\n\n"
                   f"{table}\n")
    print(table)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
