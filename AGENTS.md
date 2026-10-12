# AGENTS.md — CareerOps

## Project
CareerOps is a job-search intelligence platform (Python backend). Modules:
1. **Tracker** – job applications, status state machine, history, reminders
2. **Match** – JD vs profile scoring API (deterministic score + optional LLM explanation)
3. **Ingestion** – scheduled listing ingestion from legitimate sources only
4. **Analytics** – skills demand, salary ranges, posting trends
Goal: the strongest portfolio repo for Python backend roles. Quality > quantity.

## Stack (do not swap without asking)
Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic, PostgreSQL 16 (+pgvector later),
Redis, Celery + Celery Beat, JWT auth (access + refresh), Pytest + pytest-asyncio + httpx,
Ruff (lint+format), mypy, uv or pip-tools for deps.
Docker Compose is used ONLY to run local Postgres and Redis (dev convenience).

## Architecture rules
- Layers: `routers → services → repositories → models`. Routers never touch the DB directly.
- Folder layout:
  ```
  app/
    main.py
    core/        # config, security, logging, deps
    db/          # session, base, migrations helpers
    modules/
      auth/ tracker/ match/ ingestion/ analytics/
        router.py  schemas.py  service.py  repository.py  models.py
    workers/     # celery app + tasks
  tests/         # mirrors app/ structure
  dashboard/     # vanilla HTML/CSS/JS frontend (no framework, no build step)
  alembic/
  docker-compose.yml  # local Postgres + Redis only
  Makefile  README.md
  ```
- Pydantic schemas separate from ORM models. Never return ORM objects directly.
- All config via environment variables (pydantic-settings). Ship `.env.example`. Never commit secrets.
- Async everywhere in the API layer; no blocking calls in request handlers.
- Every schema change = an Alembic migration. Never edit applied migrations.
- Consistent error format: `{"error": {"code": "...", "message": "..."}}`.
- Use proper HTTP status codes, pagination (`limit`/`offset` + total), and idempotent writes where relevant.
- Structured JSON logging with a request ID. Add `/health` and `/ready`.

## Working agreement
1. **Plan first.** For any task, write a short plan (files to touch, tests to add) before coding. Wait for approval on large tasks.
2. **Small steps.** One feature per step. Commit message format: `feat(tracker): add status history`.
3. **Tests with every feature.** No feature is done without tests. Target ≥ 80% coverage.
4. **Run before claiming done:** `make lint test` must pass. Show the output.
5. **Ask before** adding a dependency, changing the stack, or deleting files.
6. Don't build features not in the current phase. Note ideas in `docs/BACKLOG.md` instead.
7. Keep code readable: type hints everywhere, docstrings on services, no dead code, no giant functions.
8. Explain non-obvious design decisions in `docs/DECISIONS.md` (short ADR style) — this feeds interview answers.

## Commands (keep Makefile in sync)
- `make services` — docker compose up -d (Postgres + Redis only)
- `make run` — uvicorn app.main:app --reload
- `make worker` — celery worker; `make beat` — celery beat
- `make test` — pytest with coverage
- `make lint` — ruff check + ruff format --check + mypy
- `make lint-js` — syntax check the dashboard JS
- `make migrate` — alembic upgrade head
- `make revision m="msg"` — new alembic revision

## Out of scope (do NOT build)
Dockerfile for the app, CI/CD pipelines (GitHub Actions etc.), cloud deployment, Terraform, Kubernetes,
Prometheus/Grafana, load-testing infrastructure. These belong to a separate DevOps project.

## Hard don'ts
- Do NOT scrape LinkedIn, Naukri, Indeed or any site whose terms forbid it. Use public ATS board endpoints
  (Greenhouse/Lever), RemoteOK/Adzuna-style APIs, CSV import, or paste-a-JD only. Respect robots.txt and rate limits.
- Do NOT store plaintext passwords or log tokens/PII.
- Do NOT invent metrics for the README. Only report numbers that were actually measured.
- Do NOT use `print` for logging, `SELECT *`, or raw string-built SQL.

## Definition of done (per phase)
Code + tests passing + migration applied + README section updated + `docs/DECISIONS.md` updated + conventional commits.
