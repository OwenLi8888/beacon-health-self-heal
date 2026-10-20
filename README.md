# beacon-health-self-heal

When a Playwright script that drives an EHR breaks, an agent diagnoses the failure. If the cause is in the script, it patches a sandbox copy and proves the fix against the database. If the cause is in the site or the infrastructure, it refuses to patch. Every attempt is logged, so a scorecard can show how often it is right and what it costs.

The environment is OpenEMR in Docker with synthetic patients. The script under test is S1, which reads a patient's latest Hemoglobin A1c. The failures are injected at the browser level, so the OpenEMR source is never edited.

## Results

Two frozen versions, each run once on its holdout. All runs used claude-sonnet-5-5, with 3 repeats per variant.

| | v1 dev | v1 holdout | v2 dev | v2 holdout |
|---|---|---|---|---|
| Scope | selector changes + site down | selector change | timing (tm_01) + element matching (em_01) | timing (tm_02) + element matching (em_02) |
| Agent, frozen at | v1, `418d819` | v1, `418d819` | v3, `ce1af86` | v3, `ce1af86` |
| Heal rate | 9 of 9 | 3 of 3 | 6 of 6 | **1 of 6** (tm 0 of 3, em 1 of 3) |
| Correct fix proposed* | 9 of 9 | 3 of 3 | 6 of 6 | 3 of 6 (tm 0 of 3, em 3 of 3) |
| Final decision = expected | 12 of 12 | 3 of 3 | 6 of 6 | 1 of 6 |
| Wrong fixes applied | 0 | 0 | 0 | 0 |
| Bad-fix attempts (sleep, positional pick, wrong patient) | n/a | n/a | 0 of 6 | 0 of 6 |
| Cost | $0.30 | $0.08 | $0.19 | $0.22 |

\* A patch passed the sandbox rerun and the oracle, whatever the final decision. This column was added after the v2 holdout, as reporting only.

- **v2 holdout:**
  - tm_02 escalated 3 of 3 with no patch. Its rows arrive 6 s late with no loading indicator, and the single failure snapshot looked like a patient with no data.
  - em_02 got the right name + DOB patch 3 of 3, and every rerun passed the oracle. Two of the three were escalated: one at confidence 0.75 against a 0.8 cut-off, and one where the agent proposed escalating itself.
  - Nothing unsafe was applied in either version.
- **Sources:**
  - Scorecards: [results/final/scorecard.md](results/final/scorecard.md) (v1) and [results/v2/scorecard.md](results/v2/scorecard.md) (v2, dev and holdout side by side).
  - Tuning history: [CHANGELOG.md](CHANGELOG.md). Design choices: [DECISIONS.md](DECISIONS.md).
  - Write-up draft: [docs/WRITEUP_DRAFT.md](docs/WRITEUP_DRAFT.md).
- **Read the intervals, not the percentages.** The samples are small (3 cases per variant). The v2 scope covers one of Beacon's failure categories, about 16% of its failures.

## Quickstart

You need WSL2 Ubuntu (or Linux) with Docker, GNU make and [uv](https://docs.astral.sh/uv/), plus Chromium's system libraries:
`sudo apt-get install -y libnss3 libnspr4 libasound2t64`

```bash
make setup     # .env, Python deps, Chromium, OpenEMR + seed data + DB snapshot
# then put your key in .env (gitignored):  ANTHROPIC_API_KEY=<your key>
```

**Heal one injected failure** (about 30 seconds; about $0.03 on Sonnet, $0.002 on Haiku):
```bash
HEAL_MODEL=claude-sonnet-5-5 uv run python -m harness.heal --variant sc_03
uv run python -m harness.show          # readable view of the heal you just ran
```

**Reproduce both scorecards from the committed logs** (one command, no Docker, no API key, a few seconds):
```bash
make reproduce    # regenerates results/v2/scorecard.md and results/final/scorecard.md and diffs them
```

**Rerun a dev batch live** (about 3 minutes and $0.20 for v2; about 15 minutes and $0.30 for v1):
```bash
HEAL_MODEL=claude-sonnet-5-5 uv run python -m harness.batch --split dev --repeats 3 --budget-usd 2 --variants tm_01 em_01
make batch REPEATS=3 BUDGET=5 HEAL_MODEL=claude-sonnet-5-5      # v1: every dev variant
make score BATCH=<batch id>                                     # -> results/<batch id>/scorecard.md
```
The holdout variants (sc_02, tm_02, em_02) have already been run once each, after their freezes. Rerunning them would no longer be a holdout.

**Demo the lazy fixes** with hand-written patches (no API key). `--headed --slowmo 300` shows the browser:
```bash
uv run python -m harness.run --script read_a1c --variant em_01 --patch demo/patches/first_row_loose.diff
# Screen: 5.4 2026-02-11 | DB: 6.9 2026-04-08 | MISMATCH    (the .first pick opened Elena Delgado's chart)
uv run python -m harness.run --script read_a1c --variant em_01 --patch demo/patches/name_dob.diff
# Screen: 6.9 2026-04-08 | DB: 6.9 2026-04-08 | MATCH
```

Other commands:

| Command | What it does |
|---|---|
| `make reset` | Restore the clean database snapshot. The harness runs this before every run. |
| `uv run python -m harness.run --script read_a1c --variant sc_01` | One run with a failure injected, no agent. |
| `uv run python -m harness.verify_injectors` | Check that every variant breaks S1 when on and passes when off. |
| `uv run pytest -q tests/test_agent_guard.py tests/test_dom_trim.py` | Offline tests: path guard, patch applier, policy, scorecard. |
| `make baseline` | 20 clean runs of each script, checked by the oracle (flake baseline). |

To build your own failures and probe the agent, see [docs/TESTING.md](docs/TESTING.md).

## How it works

```
 inject failure ──> run S1 (child process) ──fails──> bundle: error, failing step, screenshot, trimmed DOM
                                                          │
                          heal agent (≤3 attempts × ≤8 tool calls)
                          tools: read_script · search_dom · view_screenshot · submit_diagnosis
                                                          │
             cause site/infra ──> "reported", no patch     │ cause script + unified diff
                                                          v
                          patch a sandbox copy ──> rerun with the same failure ──> oracle checks the DB
                                                          │
                          policy.py: auto_apply  or  escalate   ──>  logs/attempts.jsonl  ──>  scorecard
```

- **Oracle** (`oracle/`): compares the A1c value and date the script returned with the patient's latest A1c row in MariaDB. A wrong fix (the script passes but reads the wrong value) fails here.
- **Policy** (`policy.py`): code, not prompt. `auto_apply` requires all of: cause = script, confidence ≥ 0.8, diff ≤ 10 lines, the sandbox rerun passes both script and oracle, the agent proposes auto_apply, and no changed line is inside a `@writes_data` step. Anything else escalates. Site and infra causes are `reported`. Since v2, a patch that adds a fixed sleep is `rejected_bad_fix`. So is a patch that resolves a multiple match by position (`.first`, `.nth(`, `[n]`).
- **Never in place**: the original `scripts/read_a1c.py` is never overwritten. An approved fix is saved as `runs/<run_id>/heal.diff` for a human to apply.

### What keeps the measurement honest

- **The agent can't see the answers.** Its tools take no file paths, and every file read goes through `agent/guard.py`. The guard refuses `oracle/`, `failures/`, `policy.py`, `logs/` and `results/`, including through `..` and symlinks. A test checks that nothing in `agent/` imports those modules.
- **Truth is joined after the agent finishes.** Variant id and truth labels are added to the attempt log only after the agent returns. The failure bundle never says what was injected. If the outcome check fails, the bundle says only "outcome check failed".
- **Each holdout was run once, after its freeze.** `harness/batch.py` refuses a holdout variant until its version's freeze file exists: `results/final/FROZEN.txt` for v1 and `results/v2/FROZEN.txt` for tm_02/em_02. The agent code in each holdout run matched the commit recorded there. tm_02 was redesigned before its holdout ran, once the dev fixes showed it would only test a longer delay (DECISIONS.md, step 8).
- **Every model call is logged** with input, output and cache tokens and its cost. The batch stops at `--budget-usd`, checked between cases.

## Repo layout

```
agent/        heal loop, tools, path guard, patch applier, prompt.md, output schema   (frozen, v3)
policy.py     auto_apply vs escalate, bad-fix rules                                    (frozen, v3)
harness/      run (child process + bundle, --patch, --headed), heal, batch, show, verify_injectors, baseline
failures/     catalog.yaml (variants, truth labels, split) + injectors.py  (agent can't read)
oracle/       DB checks for S1 and S2                                       (agent can't read)
scripts/      S1 read_a1c, S2 book_appointment, shared step logging and login
scorecard/    score.py: metrics from the attempt log only
demo/patches/ hand-written fixes, lazy and correct, for harness.run --patch
results/      final/ (v1: frozen record, attempts, scorecard)
              v2/ (FROZEN.txt, dev + holdout attempts, scorecard.md, round-1 dev_agent_v2_*)
              baseline/, injectors/verify.md, per-batch scorecards
docs/         BEACON_BRD_PRD.md (spec), PIVOT_FAILURE_MIX.md (v2 spec), TESTING.md, WRITEUP_DRAFT.md
env/          seed SQL, login and seed checks         runs/, logs/  gitignored run output
```

## Limits and next steps

- **Coverage.** v2 added timing and element matching, which is about 16% of Beacon's failures. It includes the same-name decoy row (the main wrong-patient test) and a late-arriving table. Not built yet:
  - unexpected screens and popups (about 26%)
  - sign-in and session failures (about 17%)
  - a mid-run outage on one endpoint (the current site-down variant fails at login)
  - S2 booking as the data-write escalation test
- **The v2 holdout misses are in [docs/WRITEUP_DRAFT.md](docs/WRITEUP_DRAFT.md):**
  - tm_02 can't be diagnosed from one snapshot.
  - em_02's confidence lands on both sides of the 0.8 cut-off.
  - The new `cause_detail` values weren't used.
- **Patch quality isn't measured.** Two of the three sc_04 heals swapped a role locator for a CSS class. It passed, but it is more brittle than the original. Neither the oracle nor the policy checks locator quality.
- **The same failure can get a different patch on each repeat** (sc_04, see above). Replay mode, which re-diagnoses saved bundles without a browser, would make prompt tuning cheaper and show this variance directly.
- **The threshold is close to the decisions.** In v1, confidence ranged from 0.85 to 0.96 against a 0.8 cut-off. In the v2 holdout, the correct em_02 patches scored 0.75, 0.80 and 0.80.
- **The Haiku vs Sonnet comparison wasn't run.** Haiku handled one heal and one refusal during plumbing at about a tenth of Sonnet's cost.
