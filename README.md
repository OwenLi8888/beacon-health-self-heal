# beacon-health-self-heal

## Prerequisites
- WSL2 Ubuntu with Docker Desktop, GNU make, and [uv](https://docs.astral.sh/uv/).
- Chromium's system libraries: `sudo apt-get install -y libnss3 libnspr4 libasound2t64`

## Run
```
make setup      # env, Python deps, Chromium, OpenEMR + seed + snapshot
make reset      # restore the clean DB
uv run python -m scripts.read_a1c --first Rosa --last Delgado
uv run python -m scripts.book_appointment --first Marcus --last Bell --provider "Okoro, Nadia" \
  --type "Office Visit" --date 2026-11-03 --time 10:30
uv run pytest -q   # live tests need a fresh `make reset`
make baseline      # 20 runs each of S1 and S2, judged by the oracles -> results/baseline/
```
