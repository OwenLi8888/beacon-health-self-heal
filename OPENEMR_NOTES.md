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
