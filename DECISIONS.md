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
