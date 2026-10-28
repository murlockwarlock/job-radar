#!/usr/bin/env bash
set -Eeuo pipefail

test -f .env || { printf '%s\n' '.env is missing; copy .env.example to .env and fill secrets'; exit 1; }
docker compose up -d postgres redis
docker compose run --rm migrations
docker compose up -d api worker scheduler bot
curl --fail --retry 20 --retry-delay 2 http://127.0.0.1:8000/health
curl --fail --retry 20 --retry-delay 2 http://127.0.0.1:8000/ready
printf '%s\n' 'Job Radar is ready'
