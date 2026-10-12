# ARCHITECTURE — CareerOps (2026-10-12)

## Current state: docs-only, no app architecture instantiated
- `AGENTS.md` mandates layers: `routers → services → repositories → models`; routers never touch DB.
- Planned tree: `app/main.py`, `app/core/`, `app/db/`, `app/modules/{auth,tracker,match,ingestion,analytics}/{router,schemas,service,repository,models}.py`, `app/workers/`, `tests/` mirroring `app/`, `alembic/`.
- None of the above exists yet — greenfield build under a docs/harness shell.

## Existing structure (what IS here)
- `docs/PRD.md` — product source of truth, 15 sections, requirement IDs AUTH/TRK/MAT/ING/ANA/PLT
- `OPENCODE_PROMPTS.md` — 6 phased build prompts (0 Bootstrap … 5 Deploy)
- `deve/AGENTS.md` + `deve/CLAUDE.md` — Solo AI Product Engineering harness v1.0 (loop rails, gates, protocols)
- `deve/os/` — lifecycle, gates 1-6, roles, engineering-rules, quality-security, release-experiments, fcar-rubric, decision-architecture + `artifacts/` templates
- `deve/scripts/` — scope-check + tests, verify/secret-scan/spend-log shell
- `.opencode/` — GSD runtime (commands, agents, hooks, get-shit-done workflows/templates)

## Data flow (target, per PRD §9)
- Clients/Swagger → FastAPI (routers→services→repositories→models) → PostgreSQL / Redis / Celery+Beat.
- Pydantic schemas separate from ORM; config via pydantic-settings env; JSON logging + request ID; `/health`, `/ready`, `/metrics`.

## Entry points today
- `deve/scripts/scope-check.py --task ... --pitch ...` — only executable entry point
- `task verify|test|lint|secret-scan` — requires go-task + `.harness/` (partially missing)

## Build order implication
- Phase 0 must instantiate the target architecture before any feature phases.
- Keep harness docs read-only; app code lives in `app/`, never in `deve/`.
