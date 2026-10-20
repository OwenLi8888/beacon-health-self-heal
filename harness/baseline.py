"""Flake baseline: N clean runs of a script, each judged by its oracle.

Each run resets the DB, runs the script as a subprocess for the next case in rotation,
and checks its output against the DB. Exits non-zero unless every run passes.
Usage: uv run python -m harness.baseline --script read_a1c --runs 20
       uv run python -m harness.baseline --script book_appointment --runs 20
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import date, time as clock  # `time` is the stdlib module here
from decimal import Decimal
from pathlib import Path

from oracle import s1_read_a1c, s2_book_appointment

OUT = Path("results/baseline")

# (first, last, date of birth from env/seed/seed.sql)
S1_CASES = [("Rosa", "Delgado", "1961-03-14"), ("Marcus", "Bell", "1958-11-02"), ("Priya", "Raman", "1974-07-21"),
            ("Elena", "Delgado", "1990-01-30")]
# Weekdays inside the seeded 08:00-17:00 office hours. Both providers, 15- and 30-minute types,
# the first slot of the day, and patients who share a last name.
S2_CASES = [
    ("Marcus", "Bell", "Okoro, Nadia", "Office Visit", "2026-11-03", "10:30"),
    ("Rosa", "Delgado", "Administrator", "Established Patient", "2026-11-04", "09:00"),
    ("Elena", "Delgado", "Okoro, Nadia", "New Patient", "2026-11-05", "14:15"),
    ("Thomas", "Whitfield", "Administrator", "Preventive Care Services", "2026-11-06", "16:30"),
    ("Mei", "Tanaka", "Okoro, Nadia", "Health and Behavioral Assessment", "2026-12-01", "08:00"),
]


def run_s1(case) -> tuple[list[str], dict, callable]:
    first, last, dob = case
    def judge(out):
        return s1_read_a1c.check(first, last, Decimal(out["value"]), date.fromisoformat(out["date"]))
    return ["--first", first, "--last", last, "--dob", dob], {"patient": f"{first} {last}"}, judge


def run_s2(case) -> tuple[list[str], dict, callable]:
    first, last, provider, type_, day, at = case
    def judge(out):
        return s2_book_appointment.check(first, last, provider, type_, date.fromisoformat(day),
                                         clock.fromisoformat(at), out)
    args = ["--first", first, "--last", last, "--provider", provider, "--type", type_, "--date", day, "--time", at]
    return args, {"patient": f"{first} {last}", "provider": provider, "type": type_, "at": f"{day} {at}"}, judge


SCRIPTS = {"read_a1c": (S1_CASES, run_s1), "book_appointment": (S2_CASES, run_s2)}


def run_once(script: str, i: int) -> dict:
    cases, build = SCRIPTS[script]
    args, record, judge = build(cases[i % len(cases)])
    subprocess.run(["make", "reset"], check=True, capture_output=True)
    start = time.monotonic()
    proc = subprocess.run([sys.executable, "-m", f"scripts.{script}", *args], capture_output=True, text=True)
    record = {"run": i + 1, **record, "seconds": round(time.monotonic() - start, 1)}
    if proc.returncode != 0:
        return record | {"passed": False, "error": (proc.stderr.strip().splitlines() or ["<no stderr>"])[-1]}
    out = json.loads(proc.stdout)
    passed, detail = judge(out)
    return record | {"passed": passed, "output": out, "oracle": detail}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", choices=SCRIPTS, required=True)
    ap.add_argument("--runs", type=int, required=True)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    with open(OUT / f"{args.script}.jsonl", "w") as f:
        for i in range(args.runs):
            records.append(run_once(args.script, i))
            f.write(json.dumps(records[-1]) + "\n")
            print(json.dumps(records[-1]), flush=True)
    passes = sum(r["passed"] for r in records)
    mean = sum(r["seconds"] for r in records) / args.runs
    cases = SCRIPTS[args.script][0]
    (OUT / f"{args.script}.md").write_text(
        f"# {args.script} baseline\n\n{passes}/{args.runs} runs passed the oracle"
        f" (DB reset before each run; {len(cases)} cases rotated, listed in harness/baseline.py).\n"
        f"Mean script time: {mean:.1f}s. Per-run detail: {args.script}.jsonl.\n")
    print(f"{passes}/{args.runs} passed")
    sys.exit(0 if passes == args.runs else 1)


if __name__ == "__main__":
    main()
