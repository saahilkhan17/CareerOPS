# CONVENTIONS — CareerOps (2026-10-12)

## Mandated (per `AGENTS.md`, applies to future `app/` code)
- Layers `routers → services → repositories → models`; routers never touch DB directly
- Pydantic schemas separate from ORM models; never return ORM objects directly
- Async everywhere in API layer; no blocking calls in handlers
- Every schema change = Alembic migration; never edit applied migrations
- Error format `{"error": {"code": "...", "message": "..."}}`; proper HTTP codes; `limit/offset+total` pagination; idempotent writes where relevant
- Config via env (pydantic-settings); ship `.env.example`; never commit secrets
- Structured JSON logging + request ID; `/health` + `/ready`
- Type hints everywhere; docstrings on services; no dead code; no giant functions
- Conventional commits: `feat(tracker): add status history`
- No `print` logging, no `SELECT *`, no raw string-built SQL
- Design decisions in `docs/DECISIONS.md` (ADR style); ideas in `docs/BACKLOG.md`

## Observed in `deve/scripts/` (keep)
- `scope-check.py` — stdlib only, typed (`List[str]`, `Tuple[bool, List[str]]`), docstring + usage, `main() -> int` with `sys.exit(main())`
- Tests mirror script names (`test_scope_check.py`, `test_pre_tool_guard.py`), pytest functions, fixture-built secrets (avoid literal long secrets to stay secret-scan clean)
- Shell scripts: `set -euo pipefail`, `[script]` log prefixes, exit codes as gates

## Harness conventions (deve/, informational)
- Loop rails: `max_steps=15`, IAL debounce (no identical tool+args twice), ECT (exit-code-0 termination), FCAR fresh-context review
- Gates 1-6 per `deve/os/gates.md`; hard gates (tests/lint) no override; soft gates need documented exception in artifact
- Stakes tiering: tiny (<4h, reversible) skips Gates 4/6; default full; high-stakes + re-implementation

## Style risks
- Harness uses `task` (go-task); AGENTS.md mandates `make` — pick `make` as canonical, document mapping.
- Bash scripts assume Unix; local platform is Windows (PowerShell) — CI + Docker are the source of truth for shell gates.
