# N8C-20 — Maintenance / Freshness / Quality / Workflow-Evaluation — closeout

**Phase:** N8C-20 (Quality/Evaluation layer over N8C-17…N8C-19).
**Base commit:** `621e09b6` (N8C-19 action staging).
**Branch:** `ops/nas-second-brain-n8c-20-quality-maintenance-20260707T225036Z`.
**Schema:** V110 → **V111** (five additive quality-owned tables only).
**MCP:** 12 → **13** read-only assistant tool groups (72 → **78** tools; +6 quality).

## What this phase is

A deterministic, **read-only EVALUATION** layer. A *quality run* inspects ONE existing N8C record — an
action stage, feedback record, answer draft, research packet, workflow route, or review item — and emits
**advisory** quality findings: freshness, citation coverage, review-state consistency, source-ref validity,
policy compliance, duplication, and boundedness. Findings recommend operator review; they never apply a
change.

## What this phase is NOT (hard boundaries, all verified)

- **NOT a repairer** — no finding, event, status, route, CLI command, or MCP tool repairs, rebuilds, or
  regenerates any artifact.
- **NOT an executor** — no action execution, no scheduler, no external email/calendar/task/reminder/Slack, no
  N8D job, no `agent_bridge` import.
- **NOT a review-disposition writer** — no accept / reject / defer / dispose / close / reopen anywhere.
  `evaluated` is a *run-record lifecycle status only*.
- **NOT an upstream mutator** — `quality build --apply` writes ONLY the five `assistant_quality_*` tables;
  every other table is byte-for-byte unchanged (see `05-no-upstream-mutation.md`).
- **NOT a source reader / LLM caller** — no `source_file_read`, no `SourceContentProvider`, no source
  scan/reindex, no source-card generation, no Qwen/Ollama/live LLM.

## Result

- New V111 migration additive + idempotent; head == `LATEST_SCHEMA_VERSION` == 111; prior V100–V110
  tables/rows survive (`02-schema-v111.md`).
- Full read-only stack: schema → migrator → models → repository → evaluator → CLI → API (GET-only) → MCP
  (read-only inspection only) (`06-cli-api-mcp-exposure.md`).
- MCP surface: 13 groups / 78 tools, finality guard passes with zero violations, `ai_outputs_card_upsert`
  remains the only sanctioned remote write (`07-finality-and-naming-guard.md`, `08-tool-inventory.md`).
- 70 new N8C-20 tests green; schema-head + finality + N8C MCP regression green; schedule + forecasting
  bundles green (`09-tests.md`).
- Committed locally as `feat(nas): add n8c quality evaluation` (no AI trailer). No push, no PR, no merge.
