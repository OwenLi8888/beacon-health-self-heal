# OpenEMR notes

## Install and health (8.4.1, 2026-10-15)
- Auto-install runs on first boot when `MYSQL_HOST` and `MYSQL_ROOT_PASS` are set. Took about 18 s on this machine; log line `OpenEMR configured successfully`. Creates DB `openemr` (283 tables, `version.v_database` = 543) and the `OE_USER` admin.
- `/meta/health/readyz` returns HTTP 200 with `{"status":"setup_required","checks":{"installed":false,...,"oauth_keys":false}}` even after a successful install (DB has tables and the admin user, login works). Don't use its body as an install signal. Unverified why; likely the `installed` check looks at something set later (oauth keys?).
- The login page (`/interface/login/login.php?site=default`) renders whether or not login will work.

## Login form
- `form#login_form` POSTs to `../main/main_screen.php?auth=login&site=default` with `authUser`, `clearPass`, hidden `new_login_session_management=1`, `languageChoice=1`. No CSRF token on the login form.
- Success: HTTP 302 to `/interface/main/tabs/main.php?token_main=<token>`. Failure: HTTP 200, small body, no redirect.
- Lockout globals (defaults): `password_max_failed_logins=20`, `ip_max_failed_logins=100`, both reset after 3600 s. Failed logins are counted in `users_secure.login_fail_counter` and `ip_tracking`. Negative login tests should stay well under these.

## Labs
- Tables: `procedure_order` -> `procedure_order_code` -> `procedure_report` -> `procedure_result`. LOINC goes in `procedure_result.result_code`.
- Dashboard Labs card (`labdata_fragment.php`, loaded by AJAX with `csrf_token_form`) shows only the most recent procedure name and date, no value.
- Values: "Click here to view and graph all labdata" opens `labdata.php`; tick a code (`value_code[]=4548-4`), mode `list` shows result, range, units, date, newest first.
- `uuid` columns are NULL on fresh install and backfilled lazily (`UuidRegistry::createMissingUuids...`). Step 4: the S2 DB diff should ignore `uuid` columns.
- The chart Labs card starts collapsed unless `user_settings.labdata_ps_expand` = 1 (seeded for user 0). For a patient with no labs it says "No lab data documented." and has no link.
- `labdata.php`: the item checkboxes and List/Matrix radios have no labels. Results table header: Name | Result | Range | Units | Date | Review | Enc. Cells are padded with `&nbsp;`; abnormal results read like "+ 6.9"; Date is `YYYY-MM-DD HH:MM:SS`.

## UI frames and navigation (S1)
- Each top tab is an iframe whose `name` is set by knockout after load: `fin` (Patient Finder), `pat` (chart), `enc`, `cal`, `msg`. Playwright's `frame.name` reports `''`; `frame_locator("iframe[name='pat']")` works.
- Search: top-bar textbox "Search by any demographics" + Enter loads `dynamic_finder.php?search_any=<term>` in `fin`. Rows are links named `Last, First`; status reads "Showing 1 to N of N entries".
- Opening a row loads `demographics.php` in `pat`; the top bar heading becomes `First Last (PUBPID)`.
- After a fresh install a "Product Registration" modal covers the UI for admins; `OPENEMR_DISABLE_TELEMETRY=1` hides it.
- Opening some charts (e.g. Marcus Bell) raises a JS `alert` "New Due Clinical Reminders". Playwright scripts dismiss it automatically; the Playwright MCP browser holds it open until `browser_handle_dialog`.

## Calendar and booking (S2)
- The top menu holds two "Calendar" labels; only one is visible. The tab loads `calendar/index.php` in iframe `cal`, day view, with a "+" link and per-slot `newEvt(...)` links.
- "+" opens `add_edit_event.php` in a modal iframe with a random `name`; `iframe[src*='add_edit_event.php']` finds it. With a chart open, the Patient field is prefilled `Last, First`.
- Labelled fields: Category, Title, Facility, Billing Facility, Patient, Provider, Date. Hour and minute are two textboxes titled "Event start time"; duration is titled "Event duration in minutes" and is filled from the category (Office Visit 15, New Patient 30). Times are 24-hour, no AM/PM field.
- Provider options read `Last, First` ("Okoro, Nadia"), or just `Last` when there is no first name ("Administrator"). The calendar sidebar's provider list did not show Okoro; the dialog does. Not investigated.
- Save runs an availability check: without an In Office (cat 2) event covering the slot it asks "Provider not available, use it anyway?"; a taken slot asks "This appointment slot is already used, use it anyway?". Dismissing either leaves the dialog open. In Office/Out Of Office (cat 3) events mark the start/end of a provider's day.
- A saved booking writes `openemr_postcalendar_events` (time in `pc_startTime`, duration in seconds) plus one `patient_tracker` and one `patient_tracker_element` row. `pc_eid` can skip values (InnoDB reserves IDs on `INSERT ... SELECT`).
- `openemr_postcalendar_events` has no default for `pc_multiple` or `pc_eventDate`; the DB runs in strict mode.
- The container's grep is BusyBox: no `--include`.
