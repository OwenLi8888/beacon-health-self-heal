# Decisions

Only decisions that affect the results, or that a reviewer would ask "why not X?" about. Each compares options on cost, time and accuracy.

## Step 1: environment

### D1. OpenEMR vs a mock web app

| | OpenEMR | Mock app |
|---|---|---|
| Cost | Free | Free, but I build every page |
| Time | About 1 hour via Docker | 1 to 2 days |
| Accuracy | Real EHR mess: iframes, legacy pages, labs, calendar | Only failures I designed |

**Pick: OpenEMR.** A mock app would make the agent look better than it is.

### D2. Docker vs installing OpenEMR directly

| | Docker | Direct install |
|---|---|---|
| Cost | Already installed | Configure PHP, web server and DB by hand |
| Time | One command up, one to wipe | Hours; hard to wipe |
| Accuracy | Same on any machine | Tied to my machine |

**Pick: Docker.** Anyone can run it from a fresh clone, and I can reset to clean in minutes.

### D3. How to pin OpenEMR: version tag + digest vs `latest`

| | `8.4.1` tag + sha256 digest | `latest` / plain tag |
|---|---|---|
| Cost | If Docker Hub ever deletes the digest, setup fails until I bump it | None |
| Time | Same | Same |
| Accuracy | Byte-identical image every run. Tags are rebuilt daily, so only the digest is truly fixed | Image can change under me and break scripts for reasons I didn't inject |

**Pick: tag + digest.** 8.4.1 is the production release (8.5.0 is the dev build). An unplanned UI change would look exactly like an injected failure.

### D4. Database reset: SQL dump restore vs rebuild

| | Restore a `mariadb-dump` snapshot | Rebuild OpenEMR |
|---|---|---|
| Cost | 4.1 MB snapshot | None |
| Time | **About 5 s measured** | 5 to 10 min |
| Accuracy | Identical starting data every run | Identical, but too slow to do every run |

**Pick: dump restore.** About 100 runs per batch is about 8 minutes of resets instead of about 13 hours. The snapshot is generated per install, not committed, because OpenEMR keeps part of its encryption keys outside the DB, so a committed dump wouldn't match a fresh install. `make reset` refuses to restore a snapshot from a different install.

### D5. Readiness: real login check vs health endpoint

| | Log in for real (`env/check_login.sh`) | Health endpoint / login page loads |
|---|---|---|
| Cost | One extra script | None |
| Time | A few seconds per setup or reset | Instant |
| Accuracy | Proves login actually works | OpenEMR's `/meta/health/readyz` says `"installed": false` even when installed, and the login page renders even when login is broken |

**Pick: real login.** Neither shortcut proves the thing every script depends on. A broken login would show up later as fake script failures.

## Step 2: patient data

### D6. Scripted SQL seed vs Synthea import

| | SQL seed (`env/seed/seed.sql`) | Synthea + `openemr:ccda-import` |
|---|---|---|
| Cost | About 60 lines of SQL | Second container with Java, CCDA generation, Carecoordination module |
| Time | Under an hour | Well over an hour (image has no Java, Synthea or devtools) |
| Accuracy | Values chosen by hand, so expected results are known before any run | Random values, read back after import |

**Pick: SQL seed.** The oracle needs known values, and each patient covers a case later steps test (latest isn't max, newest inserted first, shared last names, labs but no A1c, no labs).

## Setup notes (minor)
- **MariaDB 12.3.3 (pinned by digest)** over MariaDB 11.8 LTS or MySQL 8: it's the exact pair OpenEMR's own production compose file ships and tests.
- **Reset restores the DB only**, not OpenEMR's file storage. The scripts don't upload files; revisit if one ever does.
- **Ports 8300/9300** instead of 80/443, to avoid clashing with Windows services.
- **`make setup` copies `.env.example` to `.env` if missing**, so there are no manual steps. The example holds only local test passwords and a blank API key.
- **`make setup` snapshots only a DB volume it just created**, and refuses if an existing volume has no matching snapshot. Otherwise deleting `env/snapshot/` would silently turn a used DB into the "clean" baseline. Cost: recovering means `docker compose down -v` (about 1.5 min) or an explicit `make snapshot`.
- **DB dumps run inside the database container**, so nothing extra is installed in WSL and no password appears on a host command line.
- **WSL2 over Windows; Python over TypeScript; Claude Code for build steps, Cursor for small edits.**

## Step 3: S1 script and oracle

### D7. Oracle DB access: PyMySQL over a localhost port vs `docker exec mariadb`

| | PyMySQL on `127.0.0.1:${DB_HOST_PORT}` | `docker exec` + parse CLI output |
|---|---|---|
| Cost | One pinned dependency; DB port open on localhost only | None |
| Time | Same | Same |
| Accuracy | Typed rows (`datetime`, exact strings) | Tab-separated text to re-parse; NULL vs empty is easy to get wrong |

**Pick: PyMySQL.** The oracle is the judge, so it shouldn't depend on parsing text. Step 4's DB diff reuses the same connection.

## Step 3 notes (minor)
- **Product-registration modal disabled with `OPENEMR_DISABLE_TELEMETRY=1`** in compose. It blocked the UI after every reset; scripting a dismiss click would be noise unrelated to any failure we inject.
- **Labs card expanded by default via `user_settings` in the seed.** With no row OpenEMR renders it collapsed and its link is hidden. Having the script toggle it would flip a saved preference and depend on prior state.
- **Patient row picked by exact `Last, First` link name**, raising on 0 or more than 1. Searching "Delgado" returns Rosa and Elena; "first row" would read the wrong patient.
- **Baseline rotates the 4 A1c patients and runs the script as a subprocess** after a reset each run. Rotation covers latest-isn't-max, newest-inserted-first and shared last names; a subprocess matches how the harness will run scripts.

## Session A (PRD v0.2): S2 script and oracle

### D8. "Provider not available" confirm: seed office hours vs accept the confirm in the script

| | Seed In/Out Of Office events | Script accepts the confirm |
|---|---|---|
| Cost | 12 lines of seed SQL, full rebuild once | One dialog handler |
| Time | Same | Same |
| Accuracy | Valid slots save with no prompt; a taken slot or after-hours slot still prompts, and the dismissed prompt fails the save step | The same handler would also click through "slot already used" and double-book silently |

**Pick: seed office hours** (08:00 to 17:00, every workday, both providers). OpenEMR shows the prompt on Save whenever the provider has no In Office time covering the slot.

### D9. "No other rows changed": diff against a second copy of the snapshot vs capturing state before each run

| | `openemr_snap` schema, diffed in SQL with `EXCEPT ALL` | Harness captures rows before the run |
|---|---|---|
| Cost | `make snapshot` also loads the clean DB into `openemr_snap` | The before-copy has to live outside the DB the agent can affect, and the harness has to remember to take it |
| Time | About 6 s per check (283 tables) | Similar, plus the capture |
| Accuracy | Compares to the literal snapshot; nothing the run does can move the baseline | Baseline already includes whatever ran before the capture |

**Pick: `openemr_snap`.** Two column kinds are ignored because page views change them on their own: `uuid` (lazy backfill) and `ON UPDATE CURRENT_TIMESTAMP` columns (bumped by that backfill). A real edit to any other column still shows.

### D10. Tables a booking may touch

- **Must change:** `openemr_postcalendar_events` +1 (right patient, provider, type, date, time, duration, not repeating), and `patient_tracker` / `patient_tracker_element` +1 each, pointing at that appointment.
- **May gain rows, never lose or change them:** the 10 tables a read-only S1 run also writes (audit log, session/login tracking, uuid and contact backfill, UI settings, recent patients, reminder log). The list comes from diffing an S1 run, so it is session noise, not booking behaviour. `sequences` (ID counter) may change in place.
- **Everything else must be identical.** Cost: if OpenEMR starts writing a new noise table, the oracle fails closed and the list needs a reviewed addition.

## Session A notes (minor)
- **S2 returns what the form holds just before Save, read back from the fields**, not its arguments. The oracle also checks the return value against the request, so a script that fills the wrong field can't pass by echoing its inputs.
- **The patient comes from the open chart** (the "+" dialog prefills it). The script checks the prefilled name is exactly `Last, First` and raises otherwise.
- **`@writes_data` marks the save step**, and `step_start` logs `"writes_data": true`. The step behaves the same; the policy reads the mark later.
- **S2 reuses `search_patient` / `open_chart` from `scripts/read_a1c.py`** rather than moving them to `common.py`. That's the smallest diff, and it leaves S1, which already passed its baseline, unchanged.
- **Fixed future weekday dates in the baseline.** The OpenEMR container runs on UTC, so "today" there is a day ahead of Toronto in the evening; fixed dates avoid that.

## Block 1 (PRD v0.3): harness, injector, catalog

### D11. Selector variants: hit the locators S1 uses vs literal id/class renames

| | Drift on S1's own handles (placeholder, link role, button text, wrapping table) | Rename an id / class |
|---|---|---|
| Cost | Each variant needs the exact rendered string | Trivial |
| Time | Same | Same |
| Accuracy | All 4 break S1 and are 1-to-2 line heals | S1 never selects by id or class, so these don't break it |

**Pick: drift on S1's handles.** Adding an id selector to S1 just so a rename can break it would change a baselined script to fit the test. That role/text locators survive id and class renames is a finding for the write-up.

### D12. Script runs in a harness subprocess (`harness/child.py`) vs in the parent process vs the script's own `main()`

| | Child process loads the script by path | In process | Script's `main()` |
|---|---|---|---|
| Cost | About 80 lines | Less | None |
| Time | Same | Same | Same |
| Accuracy | A crash or hang can't take down a batch; a sandbox copy runs the same way | A wedged browser kills the batch | Injection would have to live in agent-editable code |

**Pick: child process.** The failing step comes from the scripts' own `step_end ok=false` events (stderr tee), so nothing in `scripts/` changed.

## Block 1 notes (minor)
- **Ground truth never goes in `runs/<id>/`.** The variant, labels and oracle detail go only to `logs/runs.jsonl`. An oracle failure writes an `error.json` that says only "outcome check failed", so the expected value can't leak.
- **`context.route` misses requests that arrive by redirect.** Verified: `main.php`, reached by a 302 after the login POST, is never routed. sc_01 uses `add_init_script` with a MutationObserver instead. Every injector counts its hits, and a run with 0 hits is flagged, so a variant that silently does nothing can't pass as a break.
- **Trimmed DOM = every visible frame, live-DOM walk.** Hidden nodes are judged by computed style, which a cloned tree loses. Dropped: scripts, styles, hidden inputs (CSRF), and all attributes except id/class/name/type/value/placeholder/role/aria-*/href/title/for/onclick and a few form states. If the total is over 30 KB, the largest frame is cut and the cut is marked. Measured 0.2 to 24.6 KB on the 5 variants. Session tokens in frame URLs are redacted.
- **`sd_01` is 502 on every request**, so it fails at `login`. A mid-run outage on one endpoint is more realistic; it's next if site_down gets more variants.
- **`results/injectors/verify.md` names variants.** The block 2 path guard has to deny `results/` as well as `oracle/`, `failures/`, `policy.py` and `logs/`.
- **No Playwright trace zip yet.** v0.3 block 1 doesn't ask for one, and a trace would record the route rewrites, which the agent must not see.
