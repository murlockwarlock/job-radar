#!/usr/bin/env bash
set -Eeuo pipefail

dump_file="${1:-}"
test -n "${dump_file}" || { printf '%s\n' 'Usage: scripts/restore.sh backups/file.dump'; exit 1; }
test -f "${dump_file}" || { printf '%s\n' "Backup not found: ${dump_file}"; exit 1; }
read -r -p "Restore ${dump_file} and replace database? type RESTORE: " confirmation
test "${confirmation}" = RESTORE || { printf '%s\n' 'Cancelled'; exit 1; }
docker compose stop api worker scheduler bot
docker compose exec -T postgres dropdb -U jobradar --if-exists jobradar
docker compose exec -T postgres createdb -U jobradar jobradar
docker compose exec -T postgres pg_restore -U jobradar -d jobradar --clean --if-exists < "${dump_file}"
docker compose run --rm migrations
docker compose up -d api worker scheduler bot
