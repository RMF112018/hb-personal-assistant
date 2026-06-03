# 84 — Phase 08B: Brief Open, Delivery Status & Receipts (Prompt 12)

**Status:** Implemented (additive). Schema **V33 → V34** (one new table); package stays `1.3.0`.
**Baseline:** atop `50222a1` (08B Prompt 11; 08A closeout `954a518` is ancestor).
**Scope:** A dry-run-by-default **brief-open** action (real-but-policy-gated `open`), a read-only
**consolidated delivery status**, and a read-only **receipts** list, plus a V34 open-receipt ledger
and a proof-backed `daily_brief_open` gate. `automation_execution` stays the only deferred 08B gate.

## Context

Prompts 09–11 produce the brief's local artifacts: delivered to the vault (V31), rendered to HTML
(V32), notified locally (V33). What was missing is (a) **opening** the produced artifact, (b) a
**consolidated, open-aware status** across the four stages, and (c) a **receipts** view. A
per-surface `delivery-status` CLI already exists from Prompt 09 (`evaluate_daily_brief_delivery`);
this prompt's "delivery-status workflow" is the **new consolidated `brief-status`** — the P09 command
is unchanged.

## Design

New module `construction/second_brain/daily_brief_open.py` (mirrors the notify fail-closed pattern;
injects `db_path`/`now`/`opener`/`policy_open`/`vault_brief_dir`/`html_dir`; reuses
`read_latest_daily_brief_runs`, `daily_brief/output.py::resolve_brief_path`,
`PathPolicy().get_html_dir`):

- `_default_opener(path)` — macOS `open` via `subprocess.run(["open", path], check=False)` (darwin-
  guarded). **Injectable** (tests never launch an app). `_policy_open_enabled(seed)` reads
  `daily_brief_open.open` (default `False`). Mirrors `daily_brief_notify`.
- `_artifact_present(...)` — target produced? (`vault` → a V31 `delivery_status='delivered'` row;
  `html` → a V32 `render_status='rendered'` row).
- `evaluate_brief_open(*, target='vault', …)` — read-only → `OPEN_NEVER_GENERATED` / `OPEN_BLOCKED` /
  `OPEN_STALE` / `OPEN_NOT_AVAILABLE` / `OPEN_ALREADY_OPENED` / `OPEN_ELIGIBLE`.
- `run_brief_open_agent(mode=…, target=…, opener=…, policy_open=…, emit_receipt=…)` — **dry-run
  default** previews the would-be `open` (no launch); **apply** (only when eligible): policy off →
  `OPEN_DISABLED_BY_POLICY` (no `open`, no receipt), else `opener(path)` → `OPEN_COMPLETED` + a V34
  receipt. The optional V28 agent receipt (`agent_id='daily_brief_open_agent'`) is emit-gated.
- `evaluate_brief_delivery_status(…)` — **read-only consolidated** lifecycle over V26 +
  V31/V32/V33/V34: `delivered`/`rendered`/`notified`/`opened` booleans + `STATUS_NEVER_GENERATED` /
  `STATUS_NOT_DELIVERED` / `STATUS_DELIVERED` / `STATUS_PARTIAL` / `STATUS_COMPLETE`.
- `list_brief_receipts(…)` — **read-only** metadata list across the four ledgers (surface, brief_date,
  status, reason_code, redacted path, created_utc).
- `build_brief_open_proof()` drives the gate across every open path + the status transitions
  (NOT_DELIVERED → DELIVERED → COMPLETE) + a receipts-list assertion, with a values-only no-raw scan.

### Schema (V34) / safety / gate / policy / CLI

- `migrator.py`: `LATEST_SCHEMA_VERSION 33 → 34`; new `daily_brief_open_receipts` — metadata only
  (redacted path + a path **hash**), **`CHECK(open_target IN ('vault','html'))`** pins the targets to
  the two local artifacts, `mode IN ('dry_run','apply')`, FK to `daily_brief_runs`, the 9 standard
  `CHECK(col = 0)` guards. Registered in `safety._PHASE_08A_TABLES`.
- `data_quality.py`: new `daily_brief_open` proof-gate → **pass**; phase-08b-gates → **15 pass /
  0 warning / 0 fail / 1 deferred**.
- Policy seed + both contracts updated with the eight `OPEN_*` + five `STATUS_*` reason codes + the
  gate; lifecycle `table_count 150 → 151` + the new table entry (`v: V34`). Seed
  `daily_brief_open.open` defaults to `false` (fail-closed).
- CLI: `second-brain automation open-brief` (apply-capable, **dry-run default**, `--target
  vault|html`, `--brief-date`, `--emit-receipt` off by default), `brief-status` (read-only
  consolidated), `receipts` (read-only list, `--brief-date`/`--limit`).

## Guardrails

Local only — `open` targets the two local artifacts (`open_target` CHECK); no email/Slack/Teams/SMS/
push/webhook/Graph `sendMail`. Dry-run is the default; apply is fail-closed behind
`daily_brief_open.open` (default off → `OPEN_DISABLED_BY_POLICY`, no `open`). Receipts store only a
redacted path + a path hash (no raw content); the consolidated status + receipts list read metadata
only; 9 guard `CHECK(col = 0)` columns. No external writeback/delivery. Phase 08A guardrails preserved
(phase-08a-gates 8/1/0/3; no-writeback proof passes at schema 34).

## Known limitations / next

- `automation_execution` stays deferred — the final executor + morning-orchestrator wiring.
- Real `open` only fires on a Mac with `daily_brief_open.open=true`; never in the suite (injected
  fake opener). Apply writes the V34 receipt only on actual open; the V28 receipt is emit-gated.
  Idempotency keys on a prior `opened` receipt for (brief run, target).
- "Artifact produced" is derived from the V31/V32 terminal receipts (deterministic), not a filesystem
  stat; a delivered/rendered receipt implies the file was written by P09/P10.
