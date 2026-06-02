# 81 — Phase 08B: Daily Brief Delivery Agent (Prompt 09)

**Status:** Implemented (additive). Schema **V30 → V31** (one new table); package stays `1.3.0`.
**Baseline:** atop `aa8886e` (08B Prompt 08; 08A closeout `954a518` is ancestor).
**Scope:** A dry-run-by-default Daily Brief Delivery Agent that performs the **local-only** delivery
of an approved brief to the Obsidian vault, plus a V31 delivery-receipt ledger and a proof-backed
`daily_brief_delivery` gate. `automation_execution` stays the only deferred 08B gate.

## Context

Phase 08B built the automation substrate (launchd, locking/registry, retry/recovery, freshness,
job-health). Generation already exists end-to-end (`daily_brief/generate.py::run_daily_brief`):
assemble → synthesize → evaluate → render → write the vault note (apply-gated) → persist V26
`daily_brief_runs` + V27 `daily_brief_handoff_lines` (durable, structured, redacted). What was
missing is a **standalone delivery step**: take an already-generated, approved brief from the
durable ledger and deliver it locally, idempotently, with structured reason codes — separated from
generation so the morning orchestrator can call it as a discrete, retriable step.

## Design

New module `construction/second_brain/daily_brief_delivery.py` (injects `now`/`db_path`/
`vault_brief_dir`; reuses `read_latest_daily_brief_runs`, `read_daily_brief_handoff`, and the
existing `write_brief_output`):

- `evaluate_daily_brief_delivery` (read-only) selects the latest (or `--brief-date`) run and reports:
  - no run → `DELIVERY_NEVER_GENERATED`;
  - run blocked / `degradation_mode = blocked` → `DELIVERY_BLOCKED` (never delivered);
  - brief older than `max_age_hours` (default 36) → `DELIVERY_STALE`;
  - a prior V31 receipt records a completed delivery → `DELIVERY_ALREADY_DELIVERED` (idempotent);
  - otherwise → `DELIVERY_ELIGIBLE`.
- `run_daily_brief_delivery_agent(mode=…, emit_receipt=…)`: **dry-run default** previews and writes
  nothing. **apply** (only when eligible) renders the redacted note from the durable V27 handoff
  (`_render_brief_markdown_from_handoff`, never from a model response), writes it via
  `write_brief_output` (marker-bounded + atomic), and records a V31 delivery receipt — that ledger
  is the action's durable state and gives default idempotency. The optional V28 agent-run receipt
  (`agent_id='daily_brief_delivery_agent'`) is emit-gated, off by default.
- `build_daily_brief_delivery_proof()` drives the gate across never-generated / blocked / stale /
  eligible (dry-run) / completed (apply) / already-delivered (idempotent), asserting dry-run writes
  nothing and a values-only no-raw scan.

### Schema (V31) / gate / policy / CLI

- `migrator.py`: `LATEST_SCHEMA_VERSION 30 → 31`; new `daily_brief_delivery_receipts` (one
  metadata-only row per local-only delivery: redacted vault path + content hash + structured reason
  code). `delivery_channel` is **pinned to `obsidian_vault` by a DB CHECK** (no external channel can
  ever be recorded), `mode IN ('dry_run','apply')`, FK to `daily_brief_runs`, and the canonical 9
  no-raw/no-writeback `CHECK(col = 0)` guard columns. Registered in `safety._PHASE_08A_TABLES`.
- `data_quality.py`: new `daily_brief_delivery` proof-gate → **pass**; added to
  `PHASE_08B_GATE_NAMES` + the gates contract `required_fields`. phase-08b-gates → **12 pass /
  0 warning / 0 fail / 1 deferred**.
- Policy seed: `daily_brief_delivery` section (`channel: obsidian_vault`, `max_age_hours: 36`,
  reason codes), mirrored in the automation-policy + data-quality-gates contracts; lifecycle
  contract `table_count 147 → 148` + the new table entry (`v: V31`).
- CLI: `second-brain automation delivery-status` (read-only) and `second-brain automation deliver`
  (apply-capable, **dry-run default**, `--brief-date`, `--emit-receipt` off by default; exit 0 on
  ok, 3 on attention, 2 on invalid mode).

## Guardrails

Local-only: the sole delivery channel is the Obsidian vault, enforced in code **and** by the V31
`CHECK(delivery_channel = 'obsidian_vault')`. No email/Slack/Teams/SMS/push/webhook/Graph
`sendMail`. Dry-run is the default; apply is the explicit opt-in. Receipts are metadata-only
(redacted path + hashes + reason codes; guard columns stay at 0); `detail` / `degradation_mode` /
`output_path_redacted` are validated against forbidden tokens. The rendered note comes from the
structured V27 handoff, never a raw model response. The V31 table is in the no-writeback scan scope.
Phase 08A guardrails preserved (phase-08a-gates 8/1/0/3; no-writeback proof passes at schema 31).

## Known limitations / next

- `automation_execution` stays deferred — the final executor (retry/backoff applied to a real run,
  weekend gating, local-only alerting emission, morning-orchestrator wiring of the registry/lock +
  retry/recovery + health/freshness + **delivery** substrate). The next prompt can assume a
  dry-run-default, idempotent, local-only Delivery Agent exists, ready to be wired as the delivery
  step.
- Apply writes the V31 receipt unconditionally (the delivery ledger); the V28 agent receipt remains
  emit-gated. Idempotency keys on a prior `delivered` receipt for the brief run/date.
- Single global `max_age_hours`; per-mode cadence not differentiated.
