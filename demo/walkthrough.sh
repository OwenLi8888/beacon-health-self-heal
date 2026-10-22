#!/usr/bin/env bash
# Run every step of docs/WALKTHROUGH.md in order, printing each command before it runs.
# Usage: bash demo/walkthrough.sh [--agent] [--headed]
#   --agent   also run the three agent heals (needs ANTHROPIC_API_KEY in .env, about $0.10 on Sonnet)
#   --headed  show the browser for the script runs
# Expected failures are part of the demo, so a failing run doesn't stop the walkthrough.
set -uo pipefail
cd "$(dirname "$0")/.."

agent=0 headed=()
for arg in "$@"; do
  case "$arg" in
    --agent) agent=1 ;;
    --headed) headed=(--headed --slowmo 300) ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

step() { printf '\n\033[1m=== %s\033[0m\n' "$1"; }
show() { printf '$ %s\n' "$*"; "$@"; echo "(exit $?)"; }
bundle() {  # print the last run's bundle: error and file list
  local dir
  dir=$(tail -1 logs/runs.jsonl | python3 -c 'import sys, json; print(json.load(sys.stdin).get("bundle_dir") or "")')
  [ -n "$dir" ] || { echo "(no bundle: the run passed)"; return; }
  printf '$ ls %s && cat %s/error.json\n' "$dir" "$dir"
  ls "$dir"
  python3 -c 'import sys, json; e = json.load(open(sys.argv[1])); print(e["failing_step"], "|", e["error_type"] + ":", e["message"])' "$dir/error.json"
}
heal() {
  if [ "$agent" = 1 ]; then
    show env HEAL_MODEL=claude-sonnet-5-5 uv run python -m harness.heal --variant "$1" > /dev/null
    show uv run python -m harness.show --transcript
  else
    echo "(skipped: rerun with --agent to call the model)"
  fi
}
RUN=(uv run python -m harness.run --script read_a1c)

step "Demo 1, step 1: show the failure (em_01, duplicate patient)"
show "${RUN[@]}" --variant em_01 "${headed[@]}"
step "Demo 1, step 2: what the agent will get"
bundle
step "Demo 1, step 3: the lazy fix (first matching row) and the correct fix (name + DOB)"
show "${RUN[@]}" --variant em_01 --patch demo/patches/first_row_loose.diff "${headed[@]}"
show "${RUN[@]}" --variant em_01 --patch demo/patches/name_dob.diff "${headed[@]}"
step "Demo 1, step 4: let the agent heal it"
heal em_01

step "Demo 2, step 1: show the failure (tm_01, slow lab table)"
show "${RUN[@]}" --variant tm_01 "${headed[@]}"
step "Demo 2, step 2: why a sleep is a bad fix"
show "${RUN[@]}" --variant tm_01 --patch demo/patches/sleep_4s.diff "${headed[@]}"
show "${RUN[@]}" --variant tm_02 --patch demo/patches/sleep_4s.diff "${headed[@]}"
show "${RUN[@]}" --variant tm_02 --patch demo/patches/wait_rows.diff "${headed[@]}"
step "Demo 2, step 3: let the agent heal it"
heal tm_01
step "Demo 2, step 4: the agent's tm_01 fix (saved 22 Oct) on tm_01, then on the 6 s tm_02"
show "${RUN[@]}" --variant tm_01 --patch demo/patches/agent_tm01_expect.diff "${headed[@]}"
show "${RUN[@]}" --variant tm_02 --patch demo/patches/agent_tm01_expect.diff "${headed[@]}"

step "Demo 3, step 1: show the failure (sd_01, site down)"
show "${RUN[@]}" --variant sd_01 "${headed[@]}"
step "Demo 3, step 2: let the agent diagnose it"
heal sd_01

step "The numbers: regenerate both scorecards from the committed logs"
show make reproduce
