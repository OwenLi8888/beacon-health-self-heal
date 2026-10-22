# beacon-health-self-heal

When a Playwright script that drives an EHR breaks, an agent works out why. If the script is at fault, the agent patches a sandbox copy, and the harness proves the fix against the database before anything is approved. If the site or the infrastructure is at fault, the agent reports it and writes no patch. Every heal is logged in full, and a scorecard shows how often the agent is right and what it costs.

It runs against OpenEMR in Docker with ten synthetic patients. The script under test reads a patient's latest Hemoglobin A1c. Failures are injected in the browser, so OpenEMR's source is never edited.

**Start here:** [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md) has three short demos (duplicate patient, slow table, site down). Each step gives the command, what it does, the output to expect and what it tells you. `bash demo/walkthrough.sh` runs all of it in one go.

## Results

Two frozen versions, each run once on its holdout. All runs used claude-sonnet-5-5, 3 repeats per variant.

| | v1 dev | v1 holdout | v2 dev | v2 holdout |
|---|---|---|---|---|
| Scope | selector changes + site down | selector change | timing (tm_01) + element matching (em_01) | timing (tm_02) + element matching (em_02) |
| Agent, frozen at | v1, `418d819` | v1, `418d819` | v3, `4cd73c1` | v3, `4cd73c1` |
| Heal rate | 9 of 9 | 3 of 3 | 6 of 6 | **1 of 6** (tm 0 of 3, em 1 of 3) |
| Correct fix proposed* | 9 of 9 | 3 of 3 | 6 of 6 | 3 of 6 (tm 0 of 3, em 3 of 3) |
| Final decision = expected | 12 of 12 | 3 of 3 | 6 of 6 | 1 of 6 |
| Wrong fixes applied | 0 | 0 | 0 | 0 |
| Bad-fix attempts (sleep, positional pick, wrong patient) | n/a | n/a | 0 of 6 | 0 of 6 |
| Cost | $0.30 | $0.08 | $0.19 | $0.22 |

\* A patch passed the sandbox rerun and the oracle, whatever the final decision. This row was added after the v2 holdout, as reporting only.

What the v2 holdout says:

- **Nothing unsafe was applied in either version.** Zero wrong fixes, and no patch on a site-down case.
- **tm_02 escalated 3 of 3 with no patch.** Its rows arrive 6 s late with no loading indicator, and from a single snapshot that looks the same as a patient with no data.
- **em_02 got the right name + date-of-birth patch 3 of 3 times**, and every rerun passed the oracle. Two were still escalated: one scored 0.75 against the 0.8 cut-off, and in the other the agent proposed escalating itself. The diagnosis was fine. The confidence gate was the weak link.
- **The samples are small** (3 per variant), so read the counts, not the percentages.

Sources: [results/v2/scorecard.md](results/v2/scorecard.md) (v2, dev and holdout side by side) and [results/final/scorecard.md](results/final/scorecard.md) (v1). Tuning history is in [CHANGELOG.md](CHANGELOG.md) and design choices are in [DECISIONS.md](DECISIONS.md). `make reproduce` rebuilds both scorecards from the committed logs.

Coverage against Beacon's failure mix:

| Failure category | Share | Built | Holdout result |
|---|---|---|---|
| Unexpected screen / popup | ~26% | No | not built |
| Sign-in / session | ~17% | No | not built |
| Timing and element matching | ~16% | Yes, v2 (tm, em) | tm 0 of 3, em 1 of 3 |
| UI change (renamed selectors), not in Beacon's top 3 | n/a | Yes, v1 (sc) | sc 3 of 3 |
| Other causes, not broken down by Beacon (~41%, by subtraction) | ~41% | No | not built |

Site down (every request answers 502) is a control case, not a category. The agent has to report it and never patch. It did that 3 of 3 times on v1, and again on v3 in a live run on 22 Oct ([walkthrough, Demo 3](docs/WALKTHROUGH.md#demo-3-site-down-sd_01)).

## Quickstart

### 1. Set up (once)

You need WSL2 Ubuntu or Linux, with Docker, GNU make and [uv](https://docs.astral.sh/uv/). Chromium also needs a few system libraries:

```bash
sudo apt-get install -y libnss3 libnspr4 libasound2t64
make setup
```

`make setup` creates `.env` from `.env.example`, installs the Python packages and Chromium, starts OpenEMR and MariaDB, loads the ten patients and saves a clean database snapshot. The first run pulls the Docker images, so give it a few minutes.

To use the agent, open `.env` and paste your key into `ANTHROPIC_API_KEY=`. The file is gitignored. You don't need a key to run the scripts, the demos without the agent, or the scorecards.

To look around OpenEMR yourself, open http://localhost:8300 (the `OPENEMR_HTTP_PORT` in `.env`) and log in with `OE_USER` and `OE_PASS` from `.env`. Run `make reset` afterwards to put the database back.

Already running another copy of this stack? Before `make setup`, copy `.env.example` to `.env` and change `COMPOSE_PROJECT_NAME` and the three ports (`OPENEMR_HTTP_PORT`, `OPENEMR_HTTPS_PORT`, `DB_HOST_PORT`). Changing the project name alone still clashes on the ports.

### 2. Try it

| Goal | Command | Needs |
|---|---|---|
| Rebuild both scorecards from the committed logs | `make reproduce` | nothing (no Docker, no key) |
| Run every demo step in order | `bash demo/walkthrough.sh` (add `--agent` for the heals) | Docker (key for `--agent`) |
| Run the script with a failure switched on, no agent | `uv run python -m harness.run --script read_a1c --variant em_01` | Docker |
| Try a hand-written lazy fix and watch the oracle catch it | `uv run python -m harness.run --script read_a1c --variant em_01 --patch demo/patches/first_row_loose.diff` | Docker |
| Heal one failure (about 30 s, about $0.03) | `HEAL_MODEL=claude-sonnet-5-5 uv run python -m harness.heal --variant em_01` | Docker, key |
| Read the last heal, with every tool call | `uv run python -m harness.show --transcript` | a heal has run |
| Rerun the v2 dev batch (about 3 min, about $0.20) | `HEAL_MODEL=claude-sonnet-5-5 uv run python -m harness.batch --split dev --repeats 3 --budget-usd 2 --variants tm_01 em_01` | Docker, key |
| Score a batch | `make score BATCH=<batch id>` | a batch has run |
| Check that every variant breaks the script, and passes when switched off | `uv run python -m harness.verify_injectors` | Docker |
| Offline tests | `uv run pytest -q tests/test_agent_guard.py tests/test_policy.py tests/test_heal_log.py` | nothing |

Add `--headed --slowmo 300` to `harness.run` or `harness.heal` to watch the browser.

Don't run `harness.heal` or `harness.batch` on the holdout variants (sc_02, tm_02, em_02). Each has been run through the agent once, after its freeze, and running it again would mean it's no longer a holdout. `harness.run` is fine on any variant because it never calls the agent. To write your own failures and probe the agent, see [docs/TESTING.md](docs/TESTING.md).

## How it works

```
 inject failure ──> run script (child process) ──fails──> bundle: error, failing step, screenshot, trimmed DOM
                                                             │
                          heal agent (≤3 attempts × ≤8 tool calls)
                          tools: read_script · search_dom · view_screenshot · submit_diagnosis
                                                             │
             cause site/infra ──> "reported", no patch       │ cause script + unified diff
                                                             v
                          patch a sandbox copy ──> rerun with the same failure ──> oracle checks the DB
                                                             │
                          policy.py: auto_apply or escalate ──> logs/heals/<id>.json + logs/attempts.jsonl ──> scorecard
```

There are three pieces, and the agent can't see any of them:

- **Oracle** (`oracle/`) compares the A1c value and date the script returned with the patient's latest A1c row in MariaDB, picked by LOINC code. A wrong fix, where the script finishes but reads the wrong value, fails here.
- **Policy** (`policy.py`) is code, not a prompt. `auto_apply` needs all of these: the cause is the script, confidence is at least 0.8, the diff is 10 lines or fewer, the sandbox rerun passes both the script and the oracle, the agent itself proposes auto_apply, and no changed line sits inside a `@writes_data` step. Anything else escalates. Site and infra causes are `reported`. A patch that adds a fixed sleep, or picks one of several matches by position (`.first`, `.nth(`, `[n]`), is `rejected_bad_fix`.
- **Failure catalog** (`failures/`) holds the injectors and the answer key for each variant. The answer key is joined to the log only after the agent has finished.

`scripts/read_a1c.py` is never overwritten. An approved fix is saved as `runs/<heal_id>/heal.diff` for a person to review and apply.

## Logs

Each heal gets its own file, and a short index points to it. It's the same pattern as storing one log per run and linking it from the run's database row.

| Path | One per | Holds |
|---|---|---|
| `logs/heals/<heal_id>.json` | heal | Everything about one heal: the failure, each attempt, every model call with tokens and cost, every tool call and its result, the patch, the rerun result and the final decision |
| `logs/attempts.jsonl` | attempt (one line) | The index: decision, cost, pass or fail, and `heal_log` (the path above). The batch runner and the scorecard read only this file |
| `logs/runs.jsonl` | script run (one line) | Every run of the script, sandbox reruns included, with the oracle result |
| `runs/<run_id>/` | script run | The failure bundle the agent may read (error, screenshot, trimmed and full DOM), the sandbox copies, and `heal.diff` if a fix was approved |

`harness.show` prints a heal from the index, and `--transcript` adds the agent's step-by-step activity from the heal file. The agent can't read anything under `logs/`, because those files hold the answer key. Both `logs/` and `runs/` are gitignored. The committed copies of the scored runs are in `results/`.

## What keeps the measurement honest

- **The agent can't see the answers.** Its tools take no file paths. Every read goes through `agent/guard.py`, which refuses `oracle/`, `failures/`, `policy.py`, `logs/` and `results/`, including through `..` and symlinks. A test checks that nothing in `agent/` imports those modules.
- **Truth is joined after the agent finishes.** The failure bundle never says what was injected. If the oracle fails a run, the bundle says only "outcome check failed".
- **Each holdout ran once, after its freeze.** `harness/batch.py` refuses a holdout variant until its freeze file exists (`results/final/FROZEN.txt` for v1, `results/v2/FROZEN.txt` for v2). tm_02 was redesigned before its holdout ran, once the dev fixes showed it would only have tested a longer delay (DECISIONS.md, step 8).
- **Every model call is logged** with its input, output and cache tokens and its cost. A batch stops at `--budget-usd`.

## How I built it

1. **Spec first.** The BRD and PRD ([docs/BEACON_BRD_PRD.md](docs/BEACON_BRD_PRD.md)) were committed before any code. They define what counts as healed and what counts as a wrong fix, and they put the oracle and policy outside anything the agent can touch.
2. **Environment and a trusted baseline.** OpenEMR and MariaDB are pinned by digest. The ten seeded patients are picked to trip naive scripts: two Delgados, a latest result that isn't the highest, a patient with labs but no A1c. The A1c script passed 20 of 20 clean runs ([results/baseline/read_a1c.md](results/baseline/read_a1c.md)) before any failure was injected.
3. **v1: selector changes and site down.** Injectors, failure bundle, agent, policy and scorecard. Dev was 12 of 12 correct and the holdout 3 of 3.
4. **v2: narrowed to one of Beacon's real categories.** Timing and element matching, about 16% of Beacon's failures, with lazy fixes the policy has to reject. A tuning round caught an overfit: the agent waited for a loading message I had planted. So tm_02 was rebuilt with no message before its holdout ran.
5. **Holdout once, then report what happened**, misses included.

I built it with Claude Code, one build step per commit (`git log` reads as the step list). A reviewer subagent (`.claude/agents/reviewer.md`) checked steps against the PRD before I committed them, and DECISIONS.md records the fixes it asked for.

## Repo layout

```
agent/        heal loop, tools, path guard, patch applier, prompt.md, output schema   (frozen, v3)
policy.py     auto_apply vs escalate, bad-fix rules                                    (frozen, v3)
harness/      run, heal, batch, show, verify_injectors, baseline
failures/     catalog.yaml (variants, truth labels, split) + injectors.py  (agent can't read)
oracle/       DB checks for S1 and S2                                       (agent can't read)
scripts/      S1 read_a1c, S2 book_appointment, shared step logging and login
scorecard/    score.py: metrics from the attempt log only
demo/         walkthrough.sh, and patches/ (hand-written lazy and correct fixes, plus the agent's tm_01 fix)
results/      final/ (v1), v2/ (dev + holdout), baseline/, injectors/verify.md
docs/         WALKTHROUGH.md (demos), BEACON_BRD_PRD.md (spec), TESTING.md
env/          seed SQL, login and seed checks
runs/, logs/  run output (gitignored)
```

## Limits and next steps

- **Coverage.** Not built yet: unexpected screens and popups (~26%), sign-in and session failures (~17%), a mid-run outage on one endpoint, and booking (S2) as the data-write escalation test.
- **tm_02 can't be diagnosed from one snapshot.** A second snapshot a few seconds later, or the network log, would tell "slow" apart from "empty".
- **The agent's tm_01 fix has a hidden 5 s limit.** It waits with Playwright's `expect()`, which gives up after 5 s by default. It passes tm_01's 4 s delay and fails a 6 s one (checked on 22 Oct, [walkthrough, Demo 2 step 4](docs/WALKTHROUGH.md#step-4-where-the-agents-fix-runs-out-no-api-key)). The policy only checks that a fix passes under today's delay.
- **Confidence is too noisy to gate on.** The correct em_02 patches scored 0.75, 0.80 and 0.80 against a 0.8 cut-off. Patient-selection fixes should escalate by rule, or need agreement across 3 runs.
- **Patch quality isn't measured.** Two of the three sc_04 heals swapped a role locator for a CSS class. That passed, but it's more brittle, and neither the oracle nor the policy checks for it.
- **The same failure can get a different patch on each run.** Replay mode, which re-diagnoses saved bundles without a browser, would make prompt tuning cheaper and show this variance directly.
- **Model cost.** Every scored run used Sonnet, which sets the benchmark. The next step is to try Haiku first and escalate to Sonnet only when Haiku fails or escalates, scored against the Sonnet numbers above. During plumbing, Haiku handled one heal and one refusal at about a tenth of the cost.
