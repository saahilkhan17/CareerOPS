# TESTING — CareerOps (2026-10-12)

## Current tests (only `deve/scripts/`)
- `deve/scripts/test_scope_check.py` — 20+ cases: overlap true, stopword-only pass, synonym false-negative documented, missing-section behavior (default fail / tiny pass), numbered bullets, Non-Goals heading variant, case-insensitivity, punctuation stripping, `main()` rc 0/1, missing file rc 1
- `deve/scripts/test_pre_tool_guard.py` — 20+ cases for `.harness/hooks/pre_tool_guard.py`: curl|bash, wget|bash, rm -rf /etc, force-push, ASIA/AKIA, sk-/ghp_, clean allow, bad-JSON fail-open, chmod+x, curl|python, unquoted secret
- Runner: `python3 -m pytest scripts/ -x -q` (per `deve/Taskfile.yml: test`); `verify.sh` also runs pytest + lint + secret-scan + existence checks

## Target testing (per `AGENTS.md`, `docs/PRD.md`, `OPENCODE_PROMPTS.md` — not yet implemented)
- Pytest + pytest-asyncio + httpx (+ respx for Phase 3 HTTP mocks)
- Unit: status state machine illegal-transition 409; match scoring deterministic breakdown; dedup/idempotency/retry
- Integration: every endpoint incl. auth failures + cross-user isolation (A must not see B)
- Fixtures: `tests/fixtures/jds/` ≥20 labeled JDs with precision/recall report; saved adapter fixtures (Greenhouse/Lever)
- Coverage ≥80%; `make lint test` green before any commit claim; CI runs lint+mypy+tests (postgres service)+docker build

## Gaps / gotchas
- `test_pre_tool_guard.py` imports from `.harness/hooks/pre_tool_guard.py` which does NOT exist in repo — suite currently errors on collection
- `verify.sh` checks many `.harness/` paths that don't exist — gate fails as-is
- No `app/tests` layout yet; create `tests/` mirroring `app/` in Phase 0 with at least health-check test
- Windows local: prefer `pytest` via venv/Docker for parity; keep shell gates in CI
- Phase 0 acceptance: `make lint test` passes; CI green; health-check test proves wiring
