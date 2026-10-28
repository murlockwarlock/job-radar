.PHONY: install format lint typecheck test check compose-up compose-down migrate seed

install:
	uv sync

format:
	uv run ruff format .

lint:
	uv run ruff check .

typecheck:
	uv run mypy app

test:
	uv run python -m pytest

check: lint typecheck test

compose-up:
	docker compose up -d --build

compose-down:
	docker compose down

migrate:
	uv run alembic upgrade head

seed:
	uv run python -m app.cli seed
