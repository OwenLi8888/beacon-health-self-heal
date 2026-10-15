#!/usr/bin/env bash
# Fail loudly unless the DB holds exactly the seeded patients and the oracle's
# latest-A1c query matches the hand-written golden master.
set -euo pipefail
cd "$(dirname "$0")/.."

expected_patients=10
golden=oracle/expected_latest_a1c.tsv

sql() { docker compose exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mariadb -uroot -N -B openemr'; }

patients="$(echo 'SELECT COUNT(*) FROM patient_data;' | sql)"
if [[ "$patients" != "$expected_patients" ]]; then
  echo "check_seed: expected $expected_patients patients, found '$patients'" >&2
  exit 1
fi

actual="$(sql < oracle/queries.sql)"
if ! diff -u --label "$golden" --label "oracle/queries.sql (live DB)" "$golden" <(printf '%s\n' "$actual") >&2; then
  echo "check_seed: latest A1c per patient does not match $golden" >&2
  exit 1
fi
echo "Seed OK: $patients patients, latest A1c matches $golden"
