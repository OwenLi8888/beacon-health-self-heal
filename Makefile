SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c
.ONESHELL:
.PHONY: setup reset snapshot baseline down logs

SNAP_DIR := env/snapshot
SNAP := $(SNAP_DIR)/openemr.sql.gz
STAMP := $(SNAP_DIR)/STAMP
LOAD_ENV := set -a; . ./.env; set +a
# The DB volume's creation time ties a snapshot to one install: OpenEMR keeps
# part of its encryption keys in the sites volume, so a dump only fits its own install.
VOL_STAMP = docker volume inspect -f '{{.CreatedAt}}' "$${COMPOSE_PROJECT_NAME}_dbdata"

setup:
	if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example"; fi
	$(LOAD_ENV)
	uv sync --locked
	uv run playwright install chromium
	# Only a volume created by this run is known-clean, so only then is a snapshot taken.
	fresh=0; docker volume inspect "$${COMPOSE_PROJECT_NAME}_dbdata" >/dev/null 2>&1 || fresh=1
	docker compose up -d --wait --wait-timeout 900
	env/wait_for_login.sh
	if [ "$$fresh" = 1 ]; then
	  docker compose exec -T mysql sh -c 'MYSQL_PWD="$$MYSQL_ROOT_PASSWORD" exec mariadb -uroot openemr' < env/seed/seed.sql
	  $(MAKE) snapshot
	elif [ ! -f $(SNAP) ] || [ "$$(cat $(STAMP) 2>/dev/null)" != "$$($(VOL_STAMP))" ]; then
	  echo "setup: existing DB volume has no matching snapshot and may not be clean; refusing to snapshot it." >&2
	  echo "setup: run 'docker compose down -v && make setup' for a clean install, or 'make snapshot' if you know the DB is clean." >&2
	  exit 1
	fi
	env/check_login.sh
	env/check_seed.sh

snapshot:
	$(LOAD_ENV)
	mkdir -p $(SNAP_DIR)
	docker compose exec -T mysql sh -c 'MYSQL_PWD="$$MYSQL_ROOT_PASSWORD" exec mariadb-dump -uroot \
	  --single-transaction --routines --triggers --add-drop-database --databases openemr' \
	  | gzip > $(SNAP).tmp
	mv $(SNAP).tmp $(SNAP)
	# Clean copy for the oracle's DB diff. `reset` never touches it. Dumped without --databases,
	# so the dump names no schema and loads into openemr_snap as is.
	docker compose exec -T mysql bash -c 'export MYSQL_PWD="$$MYSQL_ROOT_PASSWORD"; set -eo pipefail; \
	  mariadb -uroot -e "DROP DATABASE IF EXISTS openemr_snap; CREATE DATABASE openemr_snap"; \
	  mariadb-dump -uroot --single-transaction openemr | mariadb -uroot openemr_snap'
	$(VOL_STAMP) > $(STAMP)
	echo "Snapshot written: $(SNAP)"

reset:
	$(LOAD_ENV)
	if [ ! -f $(SNAP) ] || [ ! -f $(STAMP) ]; then
	  echo "reset: no snapshot in $(SNAP_DIR); run make setup" >&2; exit 1
	fi
	if [ "$$(cat $(STAMP))" != "$$($(VOL_STAMP))" ]; then
	  echo "reset: snapshot belongs to a different DB volume; run make setup (fresh volume) or make snapshot (known-clean DB)" >&2; exit 1
	fi
	gunzip -c $(SNAP) | docker compose exec -T mysql sh -c 'MYSQL_PWD="$$MYSQL_ROOT_PASSWORD" exec mariadb -uroot'
	echo "DB restored from $(SNAP)"
	env/check_login.sh
	env/check_seed.sh

baseline:
	uv run python -m harness.baseline --script read_a1c --runs 20
	uv run python -m harness.baseline --script book_appointment --runs 20

down:
	docker compose down

logs:
	docker compose logs -f --tail=200
