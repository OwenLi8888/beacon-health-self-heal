# beacon-health-self-heal

When a Playwright script that drives an EHR breaks, an agent diagnoses the failure. If the cause is in the script, it patches a sandbox copy and proves the fix against the database. If the cause is in the site or the infrastructure, it refuses to patch. Every attempt is logged, so a scorecard can show how often it is right and what it costs.

The environment is OpenEMR in Docker with synthetic patients. The script under test is S1, which reads a patient's latest Hemoglobin A1c. The failures are injected at the browser level, so the OpenEMR source is never edited.

## Results (agent v1, claude-sonnet-5-5, frozen at `418d819`)

| Metric | Dev (4 variants × 3) | Holdout (1 variant × 3) |
|---|---|---|
| Heal rate | 9 of 9 (95% CI 70% to 100%) | 3 of 3 (95% CI 44% to 100%) |
| **Wrong-fix rate** (script passes, oracle fails) | 0 of 9 patched reruns | 0 of 3 patched reruns |
| Patches applied on site-down cases | 0 of 3 | n/a (none in holdout) |
| Final decision = expected decision | 12 of 12 | 3 of 3 |
| Tries per heal | 1.00 | 1.00 |
| Cost per heal | $0.034 | $0.027 |

The full scorecard is in [results/final/scorecard.md](results/final/scorecard.md). The tuning history is in [CHANGELOG.md](CHANGELOG.md), and the design choices are in [DECISIONS.md](DECISIONS.md).

**What these numbers don't show.** The sample is small, and the variants are easy: three selector changes, each fixed in one or two lines, plus one site that returns 502 on every request. The holdout is a single variant of the same failure type. Read the intervals, not the 100%. See "Limits and next steps" below.

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

**Reproduce the dev scorecard** (12 cases, about 15 minutes, about $0.30):
```bash
make batch REPEATS=3 BUDGET=5 HEAL_MODEL=claude-sonnet-5-5   # prints a batch id
make score BATCH=<batch id>                                  # -> results/<batch id>/scorecard.md
```

**Regenerate the final scorecard from the committed log** (no Docker, no API key):
```bash
uv run python -m scorecard.score --log results/final/attempts.jsonl \
  --batch b20261016-144231-c50d b20261016-145906-5c67 --out /tmp/scorecard.md
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
- **Policy** (`policy.py`): code, not prompt. `auto_apply` requires all of: cause = script, confidence ≥ 0.8, diff ≤ 10 lines, the sandbox rerun passes both script and oracle, the agent proposes auto_apply, and no changed line is inside a `@writes_data` step. Anything else escalates. Site and infra causes are `reported`.
- **Never in place**: the original `scripts/read_a1c.py` is never overwritten. An approved fix is saved as `runs/<run_id>/heal.diff` for a human to apply.

### What keeps the measurement honest

- **The agent can't see the answers.** Its tools take no file paths, and every file read goes through `agent/guard.py`. The guard refuses `oracle/`, `failures/`, `policy.py`, `logs/` and `results/`, including through `..` and symlinks. A test checks that nothing in `agent/` imports those modules.
- **Truth is joined after the agent finishes.** Variant id and truth labels are added to the attempt log only after the agent returns. The failure bundle never says what was injected. If the outcome check fails, the bundle says only "outcome check failed".
- **The holdout was run once, after the freeze.** `harness/batch.py` refuses `--split holdout` until `results/final/FROZEN.txt` exists. The agent hasn't changed since the commit recorded there.
- **Every model call is logged** with input, output and cache tokens and its cost. The batch stops at `--budget-usd`, checked between cases.

## Repo layout

```
agent/        heal loop, tools, path guard, patch applier, prompt.md, output schema   (frozen)
policy.py     auto_apply vs escalate                                                    (frozen)
harness/      run (child process + bundle), heal, batch, show, verify_injectors, baseline
failures/     catalog.yaml (variants, truth labels, split) + injectors.py  (agent can't read)
oracle/       DB checks for S1 and S2                                       (agent can't read)
scripts/      S1 read_a1c, S2 book_appointment, shared step logging and login
scorecard/    score.py: metrics from the attempt log only
results/      baseline/, injectors/verify.md, per-batch scorecards, final/
env/          seed SQL, login and seed checks         runs/, logs/  gitignored run output
```

## Limits and next steps

- **Small, easy failure set.** There are 4 selector variants (1 in holdout) and 1 site-down control. Cut to fit the 5-hour cap, in order of value:
  - `popup_modal`
  - decoy elements with the same label (the main wrong-fix test)
  - a mid-run outage on one endpoint (the current site-down variant fails at login)
  - `slow_page`
  - `login_changed`
  - S2 booking as the data-write escalation test
- **Patch quality isn't measured.** Two of the three sc_04 heals swapped a role locator for a CSS class. It passed, but it is more brittle than the original. Neither the oracle nor the policy checks locator quality.
- **The same failure can get a different patch on each repeat** (sc_04, see above). Replay mode, which re-diagnoses saved bundles without a browser, would make prompt tuning cheaper and show this variance directly.
- **The threshold is close to the decisions.** Confidence ranged from 0.85 to 0.96 against a 0.8 cut-off.
- **The Haiku vs Sonnet comparison wasn't run.** Haiku handled one heal and one refusal during plumbing at about a tenth of Sonnet's cost.
