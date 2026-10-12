# STRUCTURE — CareerOps (2026-10-12)

## Root
- `AGENTS.md` — build contract (stack, layers, commands, don'ts, DoD)
- `OPENCODE_PROMPTS.md` — phased prompts
- `docs/PRD.md` — full PRD v1.0 draft
- `deve/` — Solo harness (Taskfile, lefthook, CLAUDE.md, AGENTS.md, os/, scripts/)
- `.opencode/` — GSD local install (`command/` 67 cmds, `agents/`, `get-shit-done/`, `hooks/`, `opencode.json`, `settings.json`)
- `.planning/codebase/` — this map (new)
- `.git/` — freshly initialized 2026-10-12, no commits yet

## Key locations
- Product spec: `docs/PRD.md`
- Build phases: `OPENCODE_PROMPTS.md`
- Lifecycle/gates: `deve/os/lifecycle.md`, `deve/os/gates.md`, `deve/os/fcar-rubric.md`
- Templates: `deve/os/artifacts/{pitch,prfaq,design-note,launch-checklist,postmortem,build-log}-template.md`
- Scripts: `deve/scripts/scope-check.py`, `verify.sh`, `secret-scan.sh`, `spend-log.sh`
- Script tests: `deve/scripts/test_scope_check.py`, `test_pre_tool_guard.py`
- GSD workflows: `.opencode/get-shit-done/workflows/new-project.md`, `map-codebase.md`
- GSD templates: `.opencode/get-shit-done/templates/project.md`, `requirements.md`

## Naming conventions
- GSD commands: `gsd-<verb>-<noun>.md` in `.opencode/command/`
- OS docs: kebab-case `.md` in `deve/os/`
- Scripts: kebab-case `.py`/`.sh` in `deve/scripts/`
- Planned app code: snake_case modules per AGENTS.md layout (not yet created)

## Notable gaps (expected)
- No `app/`, `tests/`, `alembic/`, `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `Makefile`, `.env.example`, `README.md`, `docs/DECISIONS.md`, `docs/BACKLOG.md`
- No `.harness/` (referenced by `verify.sh`, `test_pre_tool_guard.py`, `Taskfile.yml`) — harness partial
- `__pycache__/` present under `deve/scripts/` — should be gitignored, not committed
