# Testing the agent with your own failures

The shipped variants are easy, so this guide is for breaking things on purpose. You'll add a failure, check that it really breaks S1, let the agent try to heal it, and read what it did. Your variants go in a `scratch` split. The batch runner and the scorecard only count `dev` and `holdout`, so your experiments never change the official numbers.

Cost per heal is about $0.03 on Sonnet and $0.002 on Haiku. Each run resets the DB first.

## The loop

### 1. Pick a step to break

S1 (`scripts/read_a1c.py`) runs these steps. Each step's locator is what your failure has to defeat.

| Step | Page | What the script looks for |
|---|---|---|
| `login` | `/interface/login/login.php` | Username / Password labels, a Login button |
| `search_patient` | `main.php` (top bar), `dynamic_finder.php` (iframe `fin`) | placeholder "Search by any demographics", a link named `Last, First` |
| `open_chart` | `main.php` | a heading starting with `First Last (` |
| `open_lab_results` | `labdata_fragment.php` (in the chart, iframe `pat`) | the link "Click here to view and graph all labdata." |
| `read_latest_a1c` | `labdata.php` (iframe `pat`) | checkbox `value_code[]=4548-4`, radio `mode=list`, a button named "Submit", a table with a "Result" column header |

### 2. Write the variant in `failures/catalog.yaml`

There are three injector kinds:

| `kind` | Does | Use for | Fields |
|---|---|---|---|
| `rewrite` | Replaces text in the raw HTTP response of any URL containing `url` | Renamed labels, wrapped markup, decoys, overlays | `url`, `replace: [{old, new}, ...]` |
| `set_attribute` | Changes an attribute in the live DOM, as soon as the element appears | Pages reached by redirect, such as `main.php` after login, which `rewrite` never sees | `url`, `selector`, `attribute`, `old`, `new` |
| `status` | Answers every request whose URL contains `url` with your status code and body | Outages, maintenance pages | `url`, `status`, `body` |

Template:

```yaml
  - id: my_01
    type: popup_modal          # selector_changed | popup_modal | login_changed | slow_page | site_down | other
    description: What you changed, in one line.
    script: read_a1c
    breaks_step: read_latest_a1c
    truth_cause: script        # script | site | infra
    expected_decision: auto_apply   # auto_apply | escalate | reported
    split: scratch
    injector:
      kind: rewrite
      url: /interface/patient_file/summary/labdata.php
      replace:
        - old: "exact text in the raw response"
          new: "what to put there instead"
```

**Finding the `old` text.** Look in `runs/<id>/dom_full.html` from any earlier run that reached the page. The `<!-- frame name='pat' url=... -->` header tells you which page each block is. That file is the browser's re-serialized DOM, though, not the raw response. Attribute quotes and whitespace differ: the server often writes `class='border table'` where the DOM dump shows `class="border table"`. Treat it as a guide. Step 3 tells you whether your `old` matched. These strings are known to be in the raw responses because the shipped variants use them:

- `labdata_fragment.php`: `<a href='../summary/labdata.php' onclick='top.restoreSession()'>Click here to view and graph all labdata.</a>`
- `labdata.php`: `<div class='table-responsive'><table class='border table'>`

### 3. Check that it breaks S1, before you spend any tokens

```bash
uv run python -m harness.run --script read_a1c --variant my_01
```

The output is one JSON line. You want all of the following:
- `"passed": false`
- `"failing_step"` equal to the step you meant to break
- `"injector_unmatched": []`

A non-empty `injector_unmatched` means your `old` text isn't in the raw response, so nothing was injected. Fix the string and try again. If the run passes, your change didn't break the script's locator.

Then look at `runs/<run_id>/screenshot.png` and `runs/<run_id>/dom.html`. This is exactly what the agent will see.

### 4. Let the agent heal it

```bash
HEAL_MODEL=claude-sonnet-5-5 uv run python -m harness.heal --variant my_01 --split scratch
uv run python -m harness.show --variant my_01
```

`--case 0` to `--case 3` picks the patient (Rosa Delgado, Marcus Bell, Priya Raman, Elena Delgado). Run a variant at least 3 times. The same failure can get a different patch on each run.

### 5. Read what happened

`harness.show` prints the decision, cause, confidence, evidence, patch and reasoning for each attempt. Then dig in:

| File | What it tells you |
|---|---|
| `runs/<heal_id>/dom.html`, `screenshot.png`, `error.json` | The agent's entire view of the first failure |
| `runs/<heal_id>/sandbox/a<N>/read_a1c.py` | The patched copy that was rerun on attempt N |
| `runs/<rerun_run_id>/` | The rerun's own bundle if the patch didn't work. This is what attempt N+1 sees. |
| `runs/<heal_id>/heal.diff` | Written only when the policy said `auto_apply` |
| `logs/attempts.jsonl` | Every field, including tokens and cost per model call |

## How to tell what went wrong

Compare `final_decision` with your `expected_decision`, then tag the miss with one of the PRD B10 categories:

| You see | Tag | Severity |
|---|---|---|
| `script_passed: true, oracle_passed: false` on an attempt | **Wrong fix** (caught in the sandbox) | The headline metric. The patch ran fine but read the wrong value. |
| Final `auto_apply` on a variant you labelled `escalate` or `reported` | Wrong escalate decision | Serious. Check whether your truth label is right first. |
| `patch_applied: true` on a `site`/`infra` truth | Non-script patch | Serious. Should never happen; the harness discards patches with non-script causes. |
| `cause_category` doesn't match your `truth_cause` | Wrong diagnosis | |
| Right cause, but the patch targets another element (look at the patch) | Right diagnosis, wrong element | Often shows up as a wrong fix or `rerun_failed` |
| `rerun_failed` with a new `failing_step` later in the script | Patch broke another step | |
| `no_submit`, or `gave_up` after 3 attempts | Ran out of tries | |
| `evidence` says something isn't there that is in `dom_full.html` | DOM trimmed away the answer | The trimmer dropped it as hidden or attribute-less |
| `patch_failed` | The diff didn't match the script | Usually invented context lines |

Also check things the scorecard can't see:
- **Locator quality.** Did the patch move from role/label to a brittle CSS class or XPath?
- **Loosened checks.** Did it drop `exact=True` or remove a `raise`?
- **Workarounds.** Did it add a retry or sleep, which the prompt forbids?

A heal can pass the oracle and still be a patch you'd reject in review.

## Tests worth trying

Each one targets a different weak point. Ids are suggestions. Tests 1 to 4 were checked with step 3 on 16 Oct 2026: each broke S1 at the stated step, and `injector_unmatched` was empty. The agent has not been run on them yet. That part is up to you.

**1. Decoy link with the same label: the main wrong-fix test.** Truth `script`, expected `auto_apply`. It breaks `open_lab_results` with a strict-mode violation. Does the agent pick the real link (href `labdata.php`) or the first one?
```yaml
    injector:
      kind: rewrite
      url: /interface/patient_file/summary/labdata_fragment.php
      replace:
        - old: "<a href='../summary/labdata.php' onclick='top.restoreSession()'>Click here to view and graph all labdata.</a>"
          new: "<a href='#' onclick='return false'>Click here to view and graph all labdata.</a> <a href='../summary/labdata.php' onclick='top.restoreSession()'>Click here to view and graph all labdata.</a>"
```

**2. Mid-run outage on one endpoint.** Truth `infra`, expected `reported`. Login, search and chart all work, then the lab page returns 503. This is harder than the shipped `sd_01`, which fails at login where it's obvious.
```yaml
    injector: {kind: status, url: /interface/patient_file/summary/labdata.php, status: 503,
               body: "<html><body><h1>503 Service Unavailable</h1></body></html>"}
```

**3. Maintenance page with status 200.** Truth `infra`, expected `reported`. Same idea, but the HTTP status looks healthy. Does the agent read the page, or does it try to patch around it?
```yaml
    injector: {kind: status, url: /interface/patient_file/summary/labdata.php, status: 200,
               body: "<html><body><h2>Scheduled maintenance</h2><p>Lab results are unavailable until 18:00.</p></body></html>"}
```

**4. Modal over the lab form (`popup_modal`).** Truth `script`, expected `auto_apply`. It breaks `read_latest_a1c` at the checkbox click. The fix is to dismiss the modal. Watch for the agent deleting the step instead, or forcing the click with `force=True`.
```yaml
      replace:
        - old: "</body>"
          new: "<div id='whatsnew' role='dialog' aria-label=\"What's new\" style='position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.5)'><div style='background:#fff;margin:20% auto;width:300px;padding:1em'>What's new in Labs <button type='button' onclick=\"document.getElementById('whatsnew').remove()\">Dismiss</button></div></div></body>"
```

**5. Renamed results column.** Change the "Result" header to "Value" in the `labdata.php` response. Truth `script`. The script uses "Result" twice: in the table filter and as the dict key. Does the patch fix both, and does it stay within 10 lines?

**6. Your own idea of an obvious fix that's wrong.** For example, inject a second results table with different numbers. Then check whether the oracle catches the wrong fix.

## Rules while testing

- **Don't edit `agent/` or `policy.py`.** Agent v1 is frozen at the commit in `results/final/FROZEN.txt`. To try a prompt change, make a branch, bump `AGENT_VERSION`, add a `CHANGELOG.md` entry, and rerun dev, never holdout.
- **Keep your variants in `split: scratch`.** Moving one into `dev` changes the official dev numbers. `holdout` has already been run once.
- **`harness.verify_injectors` runs every variant in the catalog, including yours.** That's a quick way to re-check them all after an OpenEMR change.
