# 243 — Scheduled Refresh File-Descriptor Hardening

## Why

A forced production `daily-source-refresh` (apply + live) died with
`OSError: [Errno 24] Too many open files` **while writing the scheduled receipt**; Typer's
exception hook then failed to import `typer/rich_utils.py` — a process-level file-descriptor
exhaustion, not a Procore freshness/projection verdict (the run failed before receipt write).

**Root cause.** `store/connection.py:get_connection()` opens a **new** SQLite connection on
every call (no pool/cache) and `transaction()` only commits/rolls back — it **never closes**.
The systemic `conn = _open(db_path)` / `conn = get_connection(db_path)`-without-close pattern
runs **per record** on the live path: for every retrieved item `live_sync` calls
`upsert_full_raw_payload_and_structured`, `upsert_procore_live_record`,
`record_procore_history_for_record` (→ snapshot + change-events + timeline + current-state),
and the family projection/enrichment/financial writers. Each opened a fresh connection (each
WAL connection holds up to 3 FDs) that was never closed, so thousands of records leaked tens
of thousands of descriptors until the table was exhausted mid-run.

HTTP is **not** a material leak: `procore/http_client._default_live_transport` uses
`requests.request()`, which closes its internal session/pool on return. Graph client,
subprocess (`_safe_git_sha`), and all `Path.write_text` evidence/receipt writes were already
safe.

## Connection-ownership invariant

`store/connection.py` now documents and enforces:

- `get_connection(db_path)` — opens a raw connection; the **caller** must close it.
- `transaction(conn)` — **borrows**: commit/rollback only, **never** closes.
- `open_connection(db_path)` — **owns**: opens and ALWAYS closes on every return/exception
  path (a context manager).
- `borrow_connection(conn, db_path)` — uses a caller-supplied `conn` (left open) or owns a
  fresh one; lets a parent thread one shared connection down a hot path.

## What changed

**Close what you open (no transaction-semantics change).** Each hot-path function keeps its
own independent connection and closes it via `open_connection` / `borrow_connection`. Fixed
modules: `store/procore_repositories.py`, `store/procore_history.py`,
`store/procore_enrichment.py`, `store/procore_inspection_projection.py`,
`store/procore_financials.py` (per-record writer), `procore/structured_analytics.py`
(`upsert_full_raw_payload_and_structured`), `procore/projection_engine.py`
(`backfill_endpoint_specific_from_raw_payloads`), `procore/projection_audit.py`
(`collect_inventory`, `runtime_plan_schema_mismatches`).

**Reduced churn on the nested chain.** The per-record helpers gained an optional `conn=`
parameter (via `borrow_connection`). `record_procore_history_for_record` now opens **one**
connection and threads it through its five sub-recorders (snapshot / change-events / timeline
/ current-state), so a record's history costs one connection instead of five. The
`live_sync` per-item loop keeps calling helpers with `db_path=` (each self-closing); it was
intentionally **not** wrapped in a single item-scoped connection because the loop's multiple
`continue` branches make that error-prone — an explicit safety choice. The six family
projection modules (`meeting`/`rfi`/`submittal`/`punch`/`observation`/`schedule`) open no
connections of their own; they delegate to the now-leak-free enrichment/inspection/financial
writers.

**Descriptor budget (defense-in-depth).**

- The macOS launchd plist (`scheduler/backends/launchd.py`) now emits
  `SoftResourceLimits.NumberOfFiles = 4096` and `HardResourceLimits.NumberOfFiles = 8192`.
- A forced/manual run does **not** inherit launchd limits, so `DailySourceRefreshJob.execute`
  best-effort raises `RLIMIT_NOFILE` toward 8192 at start (stdlib `resource`, never fatal).
- The scheduled receipt gained a `diagnostics` block (counts only): `fd_soft_limit`,
  `fd_hard_limit`, `open_fd_count_start`, `open_fd_count_end` — so an operator can confirm
  the run stayed within budget. Open-FD count uses `/dev/fd` (macOS) then `/proc/self/fd`
  (Linux); no `psutil` dependency.

## Scope of the close-fix

Per operator direction, the fix targets the **per-record scheduled hot-path modules** plus
the FD-limit raise. Residual low-frequency leaks remain in CLI-only / read-only helpers
(`structured_analytics` analytics commands `backfill_from_raw_payloads` /
`backfill_from_live_records` / `structured_coverage` / `structured_counts` /
`ranking_diagnostics`; `financials` read/query functions; `procore_project_health`;
`procore_freshness`). These are **not** invoked by the unattended 8:00 PM job, leak O(1)
descriptors per CLI invocation, are reclaimed at process exit, and are bounded by the raised
`NumberOfFiles` limit. They are documented here as accepted residual rather than rewritten.

## Guardrails preserved

No Procore/Graph writeback; no raw bodies / tokens / signed URLs / secrets; GET-only Procore;
local SQLite only. The change adds only `close()` calls, resource limits, and integer
diagnostics — no new external calls and no change to persisted data.

## Verification

- `tests/test_scheduled_refresh_fd_hardening.py`: the per-record write path does not grow the
  open-FD count (≤5 across 60 records + projection replay); the scheduled receipt writes
  successfully under a constrained `RLIMIT_NOFILE` after a 300-record run (the exact
  production failure); `_raise_fd_limit` lifts the soft limit; `open_connection` closes /
  `borrow_connection` reuses correctly.
- `tests/test_launcher_scheduler.py::test_launchd_plist_carries_fd_resource_limits`: the
  generated plist contains the `NumberOfFiles` limits.
- Offline proof on a read-only `/tmp` copy of the production DB (source sha256 unchanged):
  six consecutive `projection_schema_audit → backfill(apply=True) → projection_audit` cycles
  left the open-FD count flat (delta 0) while writing 10,325 primary + 25,875 child rows; the
  functional projection proof remained green.

## Operator inspection

```bash
hb-assistant scheduler status daily-source-refresh --environment production --json
```

The receipt's `diagnostics` shows the FD budget and start/end open-FD snapshots; a clean run
keeps `open_fd_count_end` well below `fd_soft_limit`.
