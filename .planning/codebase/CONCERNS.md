# CONCERNS — CareerOps (2026-10-12)

## Tech debt / breakage (fix in Phase 0)
1. `.harness/` missing but referenced by `verify.sh`, `Taskfile.yml` (lint paths, sandbox gate, telemetry), `test_pre_tool_guard.py` — either vendor minimal `.harness/` or repoint gates to `deve/` reality. Owner: Phase 0. Risk: MED.
2. `task` vs `make` dual command systems (`deve/Taskfile.yml` vs AGENTS.md `Makefile`) — divergent DoD (`task verify` vs `make lint test`). Decide: `make` canonical. Risk: LOW.
3. Bash-only gates on Windows dev machine (`npx.ps1`/`gsd-sdk.ps1` execution-policy blocks; `head` missing; shell scripts need Git-Bash/WSL). Mitigation: use `*.cmd` shims locally, CI/Docker as truth. Risk: LOW.
4. `__pycache__/` committed-tracked risk (`verify.sh` explicitly fails if `git ls-files` shows `__pycache__`/`.pyc`). Add `.gitignore` day one. Risk: LOW.
5. No git history yet (fresh `git init`, no commits, no remote). Add remote + initial commit after Phase 0 scaffold. Risk: LOW.

## Security notes
- No secrets found in docs/scripts (patterns use short fixtures; `secret-scan.sh` excludes itself). Keep scanning; never commit `.env`.
- Future high-stakes paths (auth, tokens, API keys, audit log) require adversarial cross-user tests + independent re-implementation per harness high-stakes rule.

## Scope-creep guards (from PRD + AGENTS.md)
- No scraping of forbidden boards; only Greenhouse/Lever/public API + CSV import.
- No invented README metrics; only measured numbers.
- One feature per step; ≥80% coverage; migration per schema change; decisions in `docs/DECISIONS.md`.
- PRD open Qs unresolved: third jobs API choice, hosting provider, LLM provider/cost cap, dashboard stack, demo single- vs multi-user.

## Fragile assumptions
- Local Python 3.14 vs target 3.12 — pin 3.12 in Docker/CI to avoid async/SQLAlchemy drift.
- GSD subagents not installed (`required_agents_installed: false`) — research/roadmap/planning agents unavailable; work proceeds inline until `npx get-shit-done-cc --global` or equivalent installs them.
