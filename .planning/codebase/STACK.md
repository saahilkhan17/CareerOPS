# STACK — CareerOps (2026-10-12)

No application code yet. Repo contains docs + harness only.

## Languages / runtimes
- Markdown (PRD, prompts, OS docs, templates)
- Python 3.14 (local) for `deve/scripts/` — `scope-check.py`, tests
- Bash scripts (`verify.sh`, `secret-scan.sh`, `spend-log.sh`) — not Windows-native
- Target stack (per `AGENTS.md`, not yet implemented): Python 3.12, FastAPI, Pydantic v2,
  SQLAlchemy 2.0 async, Alembic, PostgreSQL 16 (+pgvector later), Redis,
  Celery + Celery Beat, JWT (access+refresh), Pytest + pytest-asyncio + httpx,
  Ruff + mypy, Docker + Compose, GitHub Actions, uv/pip-tools

## Config / tooling
- `deve/Taskfile.yml` — go-task runner (`verify`, `test`, `lint`, `secret-scan`, `sandbox`, `fcar`, `new-project`)
- `deve/lefthook.yml` — pre-commit (secret-scan, py_compile), pre-push (verify.sh, pytest)
- `.opencode/` — GSD v1.42.3 install (67 commands, agents, hooks, `opencode.json`, `settings.json`)
- No `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `Makefile`, `app/`, `tests/` yet

## What this means for Phase 0
- Bootstrap must create: `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `Makefile`,
  `app/main.py` (+ `core/`, `db/`, `modules/`, `workers/`), `alembic/`, `tests/`, `.env.example`, CI workflow.
- Pin Python 3.12 in Docker even though local is 3.14.
- Decide: keep `deve/Taskfile.yml` harness vs canonical `Makefile` per AGENTS.md (recommend Makefile wins, Taskfile optional).
