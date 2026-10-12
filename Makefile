.PHONY: services run worker beat test lint migrate revision seed help

help:
	@echo "services - docker compose up -d (Postgres + Redis only)"
	@echo "run      - uvicorn app.main:app --reload"
	@echo "worker   - celery worker (Phase 3+)"
	@echo "beat     - celery beat (Phase 3+)"
	@echo "test     - pytest with coverage"
	@echo "lint     - ruff check + format --check + mypy"
	@echo "migrate  - alembic upgrade head"
	@echo "revision - new alembic revision (make revision m=\"msg\")"
	@echo "seed     - seed demo data (Phase 6)"

services:
	docker compose up -d

run:
	uvicorn app.main:app --reload

worker:
	celery -A app.workers.celery worker --loglevel=info

beat:
	celery -A app.workers.celery beat --loglevel=info

test:
	pytest

lint:
	ruff check app tests alembic
	ruff format --check app tests alembic
	mypy app tests

migrate:
	alembic upgrade head

revision:
	alembic revision --autogenerate -m "$(m)"

seed:
	python scripts/seed.py
