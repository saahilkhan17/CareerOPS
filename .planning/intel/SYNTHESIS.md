# Intel: Synthesis

3 documents ingested (MODE=new). Precedence SPEC > PRD > DOC.
Classifier subagents were unavailable in this runtime
(model `anthropic/claude-haiku-4-5` not installed), so classification and
synthesis were performed inline by the orchestrator following the same schemas.
Deviation recorded here for auditability.

## Source map

| Doc | Type | Role in synthesis |
|---|---|---|
| PRD.md | PRD | Requirements, phases, data model, API surface, metrics |
| AGENTS.md | SPEC | Locked technical constraints and working agreement |
| OPENCODE_PROMPTS.md | DOC | Phase execution playbook (context only) |

## Key findings

1. All three docs agree on scope, stack, phasing (0–5), and quality bars.
   The prompts doc is a direct operationalization of PRD + AGENTS.md — no divergence.
2. SPEC constraints are the binding set (see `decisions.md`); PRD acceptance
   criteria per phase become the roadmap phase goals.
3. PRD §15 open questions are deferred decisions, not conflicts — carried as
   context; MAT-7/Phase 5 will force them.
4. `deve/` harness intentionally excluded: it governs process, not product.
   Its `verify/test/lint/secret-scan` scripts remain usable as process tooling.

## Conflict summary

No BLOCKERS, no WARNINGS. 4 INFO notes in INGEST-CONFLICTS.md.
Proceeding to roadmap generation (MODE=new).
