# beacon-health-self-heal

## Prerequisites
- WSL2 Ubuntu with Docker Desktop, GNU make, and [uv](https://docs.astral.sh/uv/).
- Chromium's system libraries: `sudo apt-get install -y libnss3 libnspr4 libasound2t64`

## Run
```
make setup      # env, Python deps, Chromium, OpenEMR + seed + snapshot
make reset      # restore the clean DB
uv run python -m scripts.read_a1c --first Rosa --last Delgado
uv run pytest -q
make baseline   # 20 S1 runs judged by the oracle -> results/baseline/
```
