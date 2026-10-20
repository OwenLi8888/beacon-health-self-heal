"""Run harness: run(script, variant=None) -> RunResult, judged by script exit + outcome oracle.

On failure, runs/<run_id>/ holds the bundle the heal agent may read (error.json, screenshot.png,
dom.html, dom_full.html). Ground truth (variant, labels, oracle detail) goes only to
logs/runs.jsonl, which the agent may not read, so a bundle never says what was injected.
Usage: uv run python -m harness.run --script read_a1c [--variant sc_01] [--patch demo/patches/x.diff]
       [--headed --slowmo 300]
"""
import argparse
import json
import secrets
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from agent import patch as patching
from failures.injectors import load_catalog
from harness.baseline import S1_CASES, run_s1

RUNS = Path("runs")
LOG = Path("logs/runs.jsonl")

# script -> (cases, judge builder from harness.baseline, case -> entry kwargs)
SCRIPTS = {
    "read_a1c": (S1_CASES, run_s1, lambda c: {"first": c[0], "last": c[1], "dob": c[2]}),
}


def variant_case(script: str, variant: str | None) -> tuple | None:
    """The case a variant is pinned to by its catalog `patient` ("First Last"), or None if unpinned."""
    patient = load_catalog()[variant].get("patient") if variant else None
    if patient is None:
        return None
    cases = [c for c in SCRIPTS[script][0] if f"{c[0]} {c[1]}" == patient]
    if len(cases) != 1:
        raise ValueError(f"variant {variant}: patient {patient!r} matches {len(cases)} {script} cases")
    return cases[0]


@dataclass
class RunResult:
    run_id: str
    script: str
    variant: str | None
    passed: bool
    script_passed: bool = False  # script finished without raising; `passed` also needs the oracle
    failing_step: str | None = None
    error: str | None = None
    bundle_dir: str | None = None
    injector_unmatched: list[str] = field(default_factory=list)
    seconds: float = 0.0


def run(script: str, variant: str | None = None, case: tuple | None = None, reset: bool = True,
        script_path: Path | None = None, headed: bool = False, slowmo: float = 0) -> RunResult:
    cases, build, to_kwargs = SCRIPTS[script]
    case = case or variant_case(script, variant) or cases[0]
    _, record, judge = build(case)
    run_id = f"{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
    run_dir = RUNS / run_id
    if reset:
        subprocess.run(["make", "reset"], check=True, capture_output=True)

    start = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-m", "harness.child", "--script-path", str(script_path or Path("scripts") / f"{script}.py"),
         "--entry", script, "--kwargs", json.dumps(to_kwargs(case)), "--run-dir", str(run_dir),
         *(["--variant", variant] if variant else []), *(["--headed"] if headed else []), "--slowmo", str(slowmo)],
        capture_output=True, text=True, timeout=600)
    seconds = round(time.monotonic() - start, 1)
    lines = proc.stdout.strip().splitlines()
    if proc.returncode != 0 or not lines:
        raise RuntimeError(f"harness child crashed (exit {proc.returncode}): {proc.stderr.strip()[-2000:]}")
    child = json.loads(lines[-1])

    result = RunResult(run_id, script, variant, passed=False, script_passed=child["ok"], seconds=seconds,
                       injector_unmatched=child["injector_unmatched"])
    oracle = None
    if child["ok"]:
        passed, oracle = judge(child["output"])
        result.passed = passed
        if not passed:
            # The agent sees only that the outcome check failed, never the expected value.
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "error.json").write_text(json.dumps({
                "error_type": "OutcomeCheckFailed",
                "message": "script finished but its result did not pass the outcome check",
                "failing_step": None}, indent=2))
            result.error, result.bundle_dir = "OutcomeCheckFailed", str(run_dir)
    else:
        result.failing_step = child["failing_step"]
        result.error = f"{child['error_type']}: {child['error']}"
        result.bundle_dir = str(run_dir)

    truth = load_catalog()[variant] if variant else {}
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps({
            **asdict(result), **record,
            "failure_type": truth.get("type"), "truth_cause": truth.get("truth_cause"),
            "expected_decision": truth.get("expected_decision"), "split": truth.get("split"),
            "script_output": child.get("output"), "oracle": oracle,
            "script_path": str(script_path) if script_path else None,  # set for sandbox reruns and --patch
        }, default=str) + "\n")
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", choices=SCRIPTS, required=True)
    ap.add_argument("--variant")
    ap.add_argument("--patch", type=Path, help="hand-written diff, run on a copy of the script (demos the lazy fixes)")
    ap.add_argument("--headed", action="store_true", help="show the browser (demo)")
    ap.add_argument("--slowmo", type=float, default=0, help="ms between Playwright actions (demo)")
    a = ap.parse_args()
    script_path = None
    if a.patch:
        script_path = RUNS / "patched" / a.patch.stem / f"{a.script}.py"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(patching.apply((Path("scripts") / f"{a.script}.py").read_text(), a.patch.read_text()))
    r = run(a.script, a.variant, script_path=script_path, headed=a.headed, slowmo=a.slowmo)
    if r.script_passed:  # the oracle only judges a finished script
        print(json.loads(LOG.read_text().splitlines()[-1])["oracle"])
    print(json.dumps(asdict(r)))
    sys.exit(0 if r.passed else 1)


if __name__ == "__main__":
    main()
