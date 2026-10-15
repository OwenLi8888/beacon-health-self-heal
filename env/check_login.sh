#!/usr/bin/env bash
# Log in to OpenEMR as OE_USER over HTTP and fail loudly unless the main app loads.
# Success = login POST answers 302 to interface/main/tabs/main.php, and that page
# then loads with the session cookie without bouncing back to the login form.
# Credentials come from .env and are never printed.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a

base="http://localhost:${OPENEMR_HTTP_PORT:?OPENEMR_HTTP_PORT not set in .env}/interface"
jar="$(mktemp)"; body="$(mktemp)"
trap 'rm -f "$jar" "$body"' EXIT

curl -fsS -c "$jar" -b "$jar" -o /dev/null "$base/login/login.php?site=default"

read -r code redirect < <(curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{http_code} %{redirect_url}\n' \
  --data-urlencode "authUser=${OE_USER:?OE_USER not set in .env}" \
  --data-urlencode "clearPass=${OE_PASS:?OE_PASS not set in .env}" \
  -d new_login_session_management=1 -d languageChoice=1 \
  "$base/main/main_screen.php?auth=login&site=default")

if [[ "$code" != 302 || "$redirect" != */interface/main/tabs/main.php* ]]; then
  echo "check_login: login as $OE_USER rejected (HTTP $code, redirect '${redirect:-none}')" >&2
  exit 1
fi

main_code="$(curl -sS -c "$jar" -b "$jar" -o "$body" -w '%{http_code}' "$redirect")"
if [[ "$main_code" != 200 ]] || grep -q 'name="authUser"' "$body"; then
  echo "check_login: main app did not load after login (HTTP $main_code)" >&2
  exit 1
fi
echo "Login OK as $OE_USER at http://localhost:$OPENEMR_HTTP_PORT"
