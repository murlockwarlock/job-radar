#!/usr/bin/env bash
set -Eeuo pipefail

test -f .env || { printf '%s\n' '.env is missing'; exit 1; }
mkdir -p backups
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
docker compose exec -T postgres pg_dump -U jobradar -d jobradar --format=custom > "backups/jobradar-${stamp}.dump"
printf '%s\n' "Created backups/jobradar-${stamp}.dump"
