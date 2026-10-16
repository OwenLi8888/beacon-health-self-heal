"""Baseline for S1: N clean runs of read_a1c, each judged by the oracle.

Each run resets the DB, runs the script as a subprocess for the next of the 4 A1c patients,
and checks its output against the DB. Exits non-zero unless every run passes.
Usage: uv run python -m harness.baseline --runs 20
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import date
from decimal import Decimal
from pathlib import Path

from oracle.s1_read_a1c import check

PATIENTS = [("Rosa", "Delgado"), ("Marcus", "Bell"), ("Priya", "Raman"), ("Elena", "Delgado")]
OUT = Path("results/baseline")


def run_once(i: int) -> dict:
    first, last = PATIENTS[i % len(PATIENTS)]
    subprocess.run(["make", "reset"], check=True, capture_output=True)
    start = time.monotonic()
    proc = subprocess.run([sys.executable, "-m", "scripts.read_a1c", "--first", first, "--last", last],
                          capture_output=True, text=True)
    record = {"run": i + 1, "patient": f"{first} {last}", "seconds": round(time.monotonic() - start, 1)}
    if proc.returncode != 0:
        return record | {"passed": False, "error": (proc.stderr.strip().splitlines() or ["<no stderr>"])[-1]}
    out = json.loads(proc.stdout)
    passed, detail = check(first, last, Decimal(out["value"]), date.fromisoformat(out["date"]))
    return record | {"passed": passed, "value": out["value"], "date": out["date"], "oracle": detail}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, required=True)
    runs = ap.parse_args().runs
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    with open(OUT / "read_a1c.jsonl", "w") as f:
        for i in range(runs):
            records.append(run_once(i))
            f.write(json.dumps(records[-1]) + "\n")
            print(json.dumps(records[-1]), flush=True)
    passes = sum(r["passed"] for r in records)
    mean = sum(r["seconds"] for r in records) / runs
    (OUT / "summary.md").write_text(
        f"# S1 read_a1c baseline\n\n{passes}/{runs} runs passed the oracle"
        f" (DB reset before each run; patients rotated: {', '.join(' '.join(p) for p in PATIENTS)}).\n"
        f"Mean script time: {mean:.1f}s. Per-run detail: read_a1c.jsonl.\n")
    print(f"{passes}/{runs} passed")
    sys.exit(0 if passes == runs else 1)


if __name__ == "__main__":
    main()
