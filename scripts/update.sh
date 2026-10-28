#!/usr/bin/env bash
set -Eeuo pipefail

git diff --quiet || { printf '%s\n' 'Working tree is dirty; commit or stash changes before update'; exit 1; }
git pull --ff-only origin main
docker compose build
docker compose run --rm migrations
docker compose up -d api worker scheduler bot
if ! curl --fail --retry 20 --retry-delay 2 http://127.0.0.1:8000/ready; then
  printf '%s\n' 'Update healthcheck failed. Inspect docker compose logs and roll back with git checkout of the previous commit, then rebuild and run migrations only if compatible.' >&2
  exit 1
fi
