# Demo walkthrough

Three demos, each about two to three minutes. For every step: the command, what it does, what you should see, and what that tells you.

Run everything from the repo root after `make setup` (see the [README](../README.md#quickstart)). Steps that call the model need `ANTHROPIC_API_KEY` in `.env`. Steps marked **no API key** don't.

| Demo | Failure | What it shows |
|---|---|---|
| [1. Duplicate patient](#demo-1-duplicate-patient-em_01) | Two patients named Rosa Delgado in the search results | The agent picks the right patient, and the lazy fix gets caught |
| [2. Slow table](#demo-2-slow-lab-table-tm_01) | Lab rows arrive 4 seconds late | Why a fixed sleep is rejected, what a fix that waits for the data looks like, and where the agent's own fix runs out |
| [3. Site down](#demo-3-site-down-sd_01) | Every page returns 502 | The agent reports the outage and writes no patch |

## Run it all in one command

```bash
bash demo/walkthrough.sh            # every step without the agent (no API key, about 3 minutes)
bash demo/walkthrough.sh --agent    # the same, plus the three agent heals (about 4 minutes, about $0.10)
bash demo/walkthrough.sh --headed   # show the browser for each run (WSLg or a Linux desktop)
```

It prints each command before running it, so the output reads like the steps below. Some runs fail on purpose (that's the demo), so a failing run doesn't stop the walkthrough. It ends with `make reproduce`.

Every example output below comes from a run on 22 Oct 2026 unless it says otherwise. A live heal can give a slightly different patch, confidence or cost each time, so treat the examples as what a good result looks like, not an exact match.

## How to read a heal

`harness.heal` runs the script with the failure switched on, gives the agent the failure bundle, and checks whatever it proposes. `harness.show` prints the result. The lines that matter:

| Line | Meaning |
|---|---|
| `full log: logs/heals/<id>.json` | Everything about this heal in one file |
| `first failure: step ...` | Which step of the script broke, and the error |
| `truth: ... FINAL: ... (matches)` | The answer key from the failure catalog, joined after the agent finished, next to the decision the system made |
| `-- attempt N: <decision>` | Attempt number (3 allowed) and its outcome: `auto_apply`, `escalate`, `reported`, or `rejected_bad_fix` |
| `cause .../... conf 0.85` | The agent's diagnosis and its self-reported confidence. Auto-apply needs 0.8 or more |
| `rerun: script_passed=... oracle_passed=...` | The patched copy was rerun with the same failure. The oracle compared the value it read with the database |
| `evidence`, `patch`, `reasoning` | What the agent found, the diff it wrote, and why |
| `transcript:` | With `--transcript`: each tool call the agent made and the start of what it got back |

When the agent calls several tools in one turn, the transcript lists the calls first and then their results in the same order:

```
   transcript:
     agent calls read_script()
     agent calls search_dom({"query": "Delgado"})
       -> 1 """S1: read a patient's most recent Hemoglobin A1c (LOINC 4548-4) value and date from the chart. ...
       -> 4 match(es) for 'Delgado'; showing 4. <!-- frame name='fin' url=http://localhost:8300/interface/main/finder/dynamic_find ...
     agent calls submit_diagnosis (shown above)
```

An approved fix is never written into `scripts/`. It's saved as `runs/<heal_id>/heal.diff` for a person to apply.

---

## Demo 1: duplicate patient (em_01)

**Setup.** Patient search returns a second "Delgado, Rosa" row, placed first. It shows Elena Delgado's date of birth (1990-01-30) and links to Elena's real chart. The real Rosa was born 1961-03-14 and her latest A1c is 6.9. Elena's is 5.4.

**Why it matters.** Picking the wrong patient is the dangerous version of an element-matching failure. The run finishes and looks fine, but the value belongs to someone else. The obvious shortcut, clicking the first match, does exactly that.

### Step 1. Show the failure (no API key)

```bash
uv run python -m harness.run --script read_a1c --variant em_01 --headed
```

- **What it does:** resets the database, switches on em_01, and runs the A1c script in a visible browser.
- **You should see:** the search results with two "Delgado, Rosa" rows, then the run stops. The last line printed:
  ```
  {"run_id": "...", "variant": "em_01", "passed": false, "failing_step": "search_patient",
   "error": "AmbiguousValue: 2 patients named Rosa Delgado", "bundle_dir": "runs/<run_id>", ...}
  ```
- **What it tells you:** the script refuses to guess when two patients match. It fails loudly at step 2 instead of reading a value.

To step through it one action at a time, prefix the command with `PWDEBUG=1` and click "Step over" in the Playwright Inspector.

### Step 2. Look at what the agent will get (no API key)

```bash
ls runs/<run_id>/                 # use the bundle_dir from step 1
cat runs/<run_id>/error.json
```

Then open `runs/<run_id>/screenshot.png`.

- **You should see:** `dom.html`, `dom_full.html`, `error.json` and `screenshot.png`. The error names the failing step (`search_patient`) and `AmbiguousValue: 2 patients named Rosa Delgado`. The screenshot shows both Rosa rows with different dates of birth.
- **What it tells you:** this bundle is everything the agent sees. It isn't told what was injected. Its tools read only the bundle's trimmed DOM (`dom.html`), the screenshot and the script.

### Step 3. Try the lazy fix (no API key)

```bash
uv run python -m harness.run --script read_a1c --variant em_01 --patch demo/patches/first_row_loose.diff
```

- **What it does:** runs a copy of the script with a hand-written patch that clicks the first matching row.
- **You should see:** `Screen: 5.4 2026-02-11 | DB: 6.9 2026-04-08 | MISMATCH`, then `"script_passed": true`, `"error": "OutcomeCheckFailed"`.
- **What it tells you:** the script ran to the end and returned a value, so on exit code alone this would pass. The oracle catches it: 5.4 is Elena's A1c. This is the case the system exists to stop.

For contrast, the correct hand-written fix (match on name and date of birth):

```bash
uv run python -m harness.run --script read_a1c --variant em_01 --patch demo/patches/name_dob.diff
# Screen: 6.9 2026-04-08 | DB: 6.9 2026-04-08 | MATCH
```

### Step 4. Let the agent heal it (about 30 seconds, about $0.03)

```bash
HEAL_MODEL=claude-sonnet-5-5 uv run python -m harness.heal --variant em_01
uv run python -m harness.show --transcript
```

- **What it does:** fails the run, hands the bundle to the agent, applies its patch to a sandbox copy, reruns with the duplicate still there, checks the database, then lets `policy.py` decide.
- **You should see** (heal `20261022-014401-140f`, shortened):
  ```
  === em_01 (element_matching, split dev) on Rosa Delgado 1961-03-14 | bundle runs/20261022-014401-140f/
  full log: logs/heals/20261022-014401-140f.json
  first failure: step search_patient: AmbiguousValue: 2 patients named Rosa Delgado
  truth: cause script, expected auto_apply | FINAL: auto_apply (matches)

  -- attempt 1: auto_apply | cause script/other conf 0.85 | 3 tool calls | $0.0288
     rerun: script_passed=True oracle_passed=True diff_lines=2
     evidence: Finder frame lists two rows 'Delgado, Rosa': DOB 1990-01-30 (BH004) and DOB 1961-03-14 (BH001).
     evidence: The script takes a dob argument (1961-03-14) but search_patient never uses it, so the exact-name link locator matches both rows.
     patch:
     -    matches = finder.get_by_role("link", name=f"{last}, {first}", exact=True)
     +    matches = finder.get_by_role("row").filter(has_text=dob).get_by_role("link", name=f"{last}, {first}", exact=True)
  ```
- **What it tells you:** the agent found the root cause (the date of birth was passed in but never used) and wrote a two-line fix. The fix was proven against the same failure and the database before it was approved. A positional fix like `.first` would have been rejected by policy even if it had passed.

**Dev and held-out results** (`results/v2/dev_attempts.jsonl`, `results/v2/holdout_attempts.jsonl`). In the frozen dev batch, em_01 was auto-applied 3 of 3 times, at confidence 0.80 to 0.85, 3 tool calls and about $0.02 each. On em_02 (same failure, Marcus Bell, never used for tuning) the agent wrote the correct name + date-of-birth patch 3 of 3 times, and every rerun matched the database. Only 1 of 3 was approved: one scored 0.75 confidence, and in one the agent proposed escalating itself. Self-reported confidence is too noisy to gate patient-selection fixes on.

---

## Demo 2: slow lab table (tm_01)

**Setup.** After the lab search, the results table shows "Loading results..." and the real rows arrive 4 seconds later. The script reads straight away, finds no data rows, and fails.

**Why it matters.** Reading a page before it has finished loading is the timing half of Beacon's timing and element-matching category. The common shortcut is a fixed sleep. It passes today, breaks when the site is a little slower, and slows every run.

### Step 1. Show the failure (no API key)

```bash
uv run python -m harness.run --script read_a1c --variant tm_01 --headed
```

- **You should see:** "Loading results..." in the lab table, then `"failing_step": "read_latest_a1c"`, `"error": "ValueNotFound: A1c result table has no rows"`.
- **What it tells you:** the script raises when the value is missing. It never returns a blank or a default.

If you step through with `PWDEBUG=1`, step up to the Submit click and then press Resume. Stepping slowly past that point gives the rows time to arrive, and the run passes.

### Step 2. Show why a sleep is a bad fix (no API key)

```bash
uv run python -m harness.run --script read_a1c --variant tm_01 --patch demo/patches/sleep_4s.diff
uv run python -m harness.run --script read_a1c --variant tm_02 --patch demo/patches/sleep_4s.diff
uv run python -m harness.run --script read_a1c --variant tm_02 --patch demo/patches/wait_rows.diff
```

| Run | Delay | Result |
|---|---|---|
| 4 s sleep on tm_01 | 4 s | `MATCH` |
| 4 s sleep on tm_02 | 6 s, no loading message | fails with `ValueNotFound: A1c result table has no rows` |
| wait for a dated row on tm_02 | 6 s, no loading message | `MATCH` |

- **What it tells you:** the sleep works until the site gets two seconds slower. Waiting for the data itself works at any delay up to the wait's 30 s timeout. That's why `policy.py` rejects any patch that adds a fixed sleep, even one that passes. (`harness.run` doesn't call the agent, so running tm_02 here doesn't touch the holdout.)

### Step 3. Let the agent heal it (about 30 seconds, about $0.04)

```bash
HEAL_MODEL=claude-sonnet-5-5 uv run python -m harness.heal --variant tm_01
uv run python -m harness.show --transcript
```

- **You should see** (heal `20261022-014523-249b`): `auto_apply`, cause `script/slow_page`, confidence 0.8, 6 tool calls, $0.044. The rerun passed the script and the oracle.
- Evidence: the page HTML has only the header row, a "Loading results..." row and OpenEMR's plot row, and `table.wait_for()` resolves on the header alone.
- Patch (3 lines): import `expect`, then after the table appears, wait until some cell holds a date before reading:
  ```
  +    expect(table.get_by_role("cell").filter(has_text=re.compile(r"\d{4}-\d{2}-\d{2}"))).not_to_have_count(0)
  ```
- **What it tells you:** the agent waits for the data, not for the loading message to go away. That distinction is how an overfit was caught: an earlier version waited for the loading message, which is a hint I had planted, and the held-out version has no message.

In the frozen dev batch (`results/v2/dev_attempts.jsonl`) tm_01 was auto-applied 3 of 3 times, cause `script/slow_page`, confidence 0.80 to 0.85, 5 tool calls, about $0.04 and 26 seconds each.

### Step 4. Where the agent's fix runs out (no API key)

The patch from step 3 is saved as `demo/patches/agent_tm01_expect.diff`.

```bash
uv run python -m harness.run --script read_a1c --variant tm_01 --patch demo/patches/agent_tm01_expect.diff
uv run python -m harness.run --script read_a1c --variant tm_02 --patch demo/patches/agent_tm01_expect.diff
```

- **You should see:** `MATCH` on tm_01, then on tm_02 `"failing_step": "read_latest_a1c"`, `"error": "AssertionError: Locator expected not to have count '0'"`.
- **What it tells you:** the agent's fix has a hidden 5 s limit. Playwright's `expect()` gives up after 5 seconds by default, so it passes the 4 s delay and fails the 6 s one. The hand-written `wait_rows.diff` uses `wait_for()`, which waits 30 s. The policy can't see this: it checks that the fix passed under today's delay, not how much slower the site can get.

**Held-out result** (`results/v2/holdout_attempts.jsonl`). On tm_02 (6 seconds, no loading message) the agent went 0 of 3. From one snapshot, an empty table looks the same as a patient with no results, so it gave cause `unknown` and escalated every time, with no patch. That's the safe failure. The fix is better evidence, such as a second snapshot a few seconds later or the network log.

---

## Demo 3: site down (sd_01)

**Setup.** Every OpenEMR page returns "502 Bad Gateway", as if the customer's server were down. The script fails at login.

**Why it matters.** Not every failure is a script problem. If the site is down, patching the script changes code that was fine. The right move is to report it to whoever owns the site.

### Step 1. Show the failure (no API key)

```bash
uv run python -m harness.run --script read_a1c --variant sd_01 --headed
```

- **You should see:** the 502 page in the browser, and after about 30 seconds `"failing_step": "login"`, `"error": "TimeoutError: Locator.fill: Timeout 30000ms exceeded."`.
- **What it tells you:** the error alone ("couldn't fill the username box") looks like a script problem. Only the screenshot shows the real cause.

Don't use `PWDEBUG=1` here: debug mode turns off the timeout, so the run waits at login forever and never saves its bundle. Use `--slowmo 1000` to slow it down instead.

### Step 2. Let the agent diagnose it (about 40 seconds, about $0.02)

The failing run takes 30 seconds to time out at login. The agent itself takes under 10.

```bash
HEAL_MODEL=claude-sonnet-5-5 uv run python -m harness.heal --variant sd_01
uv run python -m harness.show --transcript
```

- **You should see** (heal `20261022-014641-f6aa`): `reported`, cause `site/site_down`, confidence 0.97, 4 tool calls, $0.019, no patch. `FINAL: reported (matches)`.
- Evidence: the screenshot shows an nginx "502 Bad Gateway" page instead of the login form, and a DOM search for "username" finds nothing.
- Transcript: `read_script`, `search_dom("username")`, `view_screenshot` (shown as `[image]`), then the submit.

**What it tells you:** the agent checked the screenshot instead of trusting the error message, reported the outage, and wrote no patch. Even if it had written one, the heal loop discards any patch on a site or infrastructure cause without applying it. sd_01 was reported 3 of 3 times on agent v1 (`results/final/attempts.jsonl`, confidence 0.96), and again on the current agent (v3) in the run above.

---

## If you want the numbers instead

```bash
make reproduce    # no Docker, no API key, a few seconds
```

This regenerates both scorecards from the committed attempt logs and diffs them against the committed copies. See [results/v2/scorecard.md](../results/v2/scorecard.md) and [results/final/scorecard.md](../results/final/scorecard.md).

The holdout variants (sc_02, tm_02, em_02) have each been run once through the agent, after their freezes. Running them through `harness.heal` or `harness.batch` again would mean they're no longer a holdout. `harness.run` on tm_02 (steps 2 and 4 of Demo 2) is fine: it never calls the agent.
