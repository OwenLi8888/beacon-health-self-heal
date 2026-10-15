#!/usr/bin/env bash
# Poll the OpenEMR login page until it serves the login form. Exit non-zero on timeout.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a

url="http://localhost:${OPENEMR_HTTP_PORT:?OPENEMR_HTTP_PORT not set in .env}/interface/login/login.php?site=default"
timeout="${1:-600}"
deadline=$((SECONDS + timeout))

while true; do
  body="$(curl -fsS --max-time 10 "$url" 2>/dev/null || true)"
  [[ "$body" == *authUser* ]] && break
  if (( SECONDS >= deadline )); then
    echo "wait_for_login: login form not served after ${timeout}s at $url" >&2
    exit 1
  fi
  sleep 5
done
echo "Login page ready: $url"
