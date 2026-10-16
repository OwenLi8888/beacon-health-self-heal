"""Run harness: run(script, variant=None) -> RunResult, judged by script exit + outcome oracle.

On failure, runs/<run_id>/ holds the bundle the heal agent may read (error.json, screenshot.png,
dom.html, dom_full.html). Ground truth (variant, labels, oracle detail) goes only to
logs/runs.jsonl, which the agent may not read, so a bundle never says what was injected.
Usage: uv run python -m harness.run --script read_a1c [--variant sc_01]
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

from failures.injectors import load_catalog
from harness.baseline import S1_CASES, run_s1

RUNS = Path("runs")
LOG = Path("logs/runs.jsonl")

# script -> (cases, judge builder from harness.baseline, case -> entry kwargs)
SCRIPTS = {
    "read_a1c": (S1_CASES, run_s1, lambda c: {"first": c[0], "last": c[1]}),
}


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
        script_path: Path | None = None) -> RunResult:
    cases, build, to_kwargs = SCRIPTS[script]
    case = case or cases[0]
    _, record, judge = build(case)
    run_id = f"{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
    run_dir = RUNS / run_id
    if reset:
        subprocess.run(["make", "reset"], check=True, capture_output=True)

    start = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-m", "harness.child", "--script-path", str(script_path or Path("scripts") / f"{script}.py"),
         "--entry", script, "--kwargs", json.dumps(to_kwargs(case)), "--run-dir", str(run_dir),
         *(["--variant", variant] if variant else [])],
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
        }, default=str) + "\n")
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", choices=SCRIPTS, required=True)
    ap.add_argument("--variant")
    a = ap.parse_args()
    r = run(a.script, a.variant)
    print(json.dumps(asdict(r)))
    sys.exit(0 if r.passed else 1)


if __name__ == "__main__":
    main()
