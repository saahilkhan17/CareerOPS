# CareerOps

Track every application, score every job description against your profile, and
see which skills the market actually wants.

Python backend API: FastAPI + SQLAlchemy (async) + PostgreSQL + Redis + Celery.
Flagship backend portfolio project — quality over quantity.

> Status: Phase 1 (Bootstrap) in progress. Endpoints today: `GET /health`, `GET /ready`.

## Quickstart

```bash
make services   # Postgres + Redis for local dev (needs Docker)
make run        # uvicorn app.main:app --reload
make migrate    # alembic upgrade head
make test       # pytest with coverage (≥80% gate)
make lint       # ruff check + format --check + mypy
```

## API overview

| Area | Endpoints | Phase |
|---|---|---|
| Ops | `GET /health`, `GET /ready` | 1 ✅ |
| Auth | `POST /auth/register, /login, /refresh, /logout`, `GET /me`, `POST/GET/DELETE /auth/api-keys` | 2 ✅ |
| Tracker | CRUD `/applications`, `POST /{id}/status`, notes, reminders, `GET /reminders/due`, `GET /export.csv` | 2 ✅ |
| Match | `POST /match`, `POST /match/{application_id}` | 3 |
| Listings | `GET /listings`, import, ingestion runs | 4 |
| Analytics | skills, salary, trends, my-gap | 5 |

Errors always look like `{"error": {"code": "...", "message": "..."}}`.

## Tech stack

Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic,
PostgreSQL 16, Redis, Celery + Beat, JWT, Pytest, Ruff, mypy, uv.

## Testing and coverage

`make lint test` must pass before every commit. Coverage gate: 80%.

## Roadmap

See `PRD.md` §5 and `.planning/ROADMAP.md`: Bootstrap → Auth+Tracker →
Match → Ingestion → Analytics+Hardening → Polish+Demo.
