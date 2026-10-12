# Ingest Conflicts

**Mode:** new · **Docs:** 3 (1 PRD, 1 SPEC, 1 DOC) · **Date:** 2026-10-12
**Precedence:** ADR > SPEC > PRD > DOC (defaults; no manifest overrides beyond type pins)

### BLOCKERS (0)

None. All destination files may be written.

### WARNINGS (0)

None. No competing variants requiring user resolution.

### INFO (4)

1. **Process deviation (auto-resolved):** `gsd-doc-classifier` / `gsd-doc-synthesizer` /
   `gsd-roadmapper` subagents failed — pinned model unavailable in this runtime.
   Classification + synthesis done inline by orchestrator using identical schemas.
   Re-run `/gsd-ingest-docs --mode merge` later if a fresh-context review is wanted.
2. **`deve/` harness excluded (auto-resolved):** process governance, not product scope.
   No product requirements drawn from it.
3. **PRD §15 open questions deferred (auto-resolved):** third jobs-API source, LLM
   provider/cost cap, dashboard stack, demo-user count. Surfaced at Phase 3 / MAT-7 /
   Phase 5 planning time, not now.
4. **Coverage honesty rule (auto-resolved):** README/PERFORMANCE numbers must be measured.
   No metrics claimed in planning docs.
