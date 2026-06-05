# 148 — Phase 07B Calendar Index Apply Robustness

Status: implemented. Supersedes the per-row apply flow in record 21.

## Problem

`graph calendar index --apply` could succeed for smaller windows, then fail on larger windows after
indexing most events with `OperationalError: unable to open database file`. DB readiness and Graph
read-only guardrails were healthy, so the likely fault boundary was local SQLite connection churn: the
old apply path opened a fresh connection/transaction for source registration, crawl-run open, every event
upsert, every attendee upsert, crawl finalization, and sync-state update.

That made the exact failing operation hard to distinguish and could leave already indexed events ambiguous
when a later local write failed.

## Fix

- `CalendarEventIndexer` now normalizes the entire fetched window before local writes.
- `ConstructionStore.apply_calendar_index_batch` applies source registration, crawl-run open/finalize,
  event upserts, attendee upserts, and sync-state update through one SQLite connection/transaction.
- On write failure, the event batch rolls back. A separate best-effort transaction records a failed
  crawl-run receipt and failed sync state with `events_indexed=0`.
- `IndexResult.failure_diagnostics` reports only safe metadata:
  `event_index_id` hash, `event_ordinal`, `operation`, and `exception_type`.
- `error_redacted` is reduced to `operation:ExceptionType`; raw exception text, DB paths, event payloads,
  subjects, locations, attendees, join URLs, and Microsoft URLs are not emitted.

## Guardrails

The Graph path remains read-only and bounded. Dry-run is still the default. No event body, join URL,
raw subject, raw location, raw organizer, raw attendee, token, or Microsoft 365 writeback is added.
Private-event minimal metadata behavior is unchanged.

## Verification

Post-change required checks:

- `python -m compileall src tests`
- `ruff check .`
- `mypy src`
- `pytest tests/test_calendar_event_indexing.py tests/test_graph_calendar_status.py tests/test_graph_calendar_endpoint_guard.py tests/test_mutation_lockout.py`
- `pytest -m "not live and not integration and not manual"`
- `hb-assistant graph calendar index --dry-run --max-items 25 --json`
- `hb-assistant graph calendar index --apply --max-items 25 --json`
- `hb-assistant graph calendar index --apply --max-items 60 --json`
- `hb-assistant graph calendar index --apply --max-items 100 --json`
- `hb-assistant graph calendar status --json --no-probe`

Acceptance requires the 60/100 apply runs to complete without `OperationalError`, and any future local
write failure to report only operation-level safe diagnostics.

## Larger-window / all-project reliability harden (post-148 / Prompt 15 follow-up) — modeled on 121 truthful reporting + 148 batch

**Objective (Prompt 15)**: Harden read-only Graph mail/calendar local sync reliability (follow-up to 148/21/04) without changing MCP exposure or writeback posture. Mail: fix all-project discover persistence/connection lifecycle bug (churn for project=None), preserve scoped, add batching + per-project diags, persist metadata/read models only. Calendar: harden larger-window apply with batching/chunking (50-100), checkpointing, per-event diags + safe finalization; preserve bounded workaround + no body/join/desc + no writeback.

**Files changed (surgical)**:
- `src/hb_assistant/construction/email/project_discovery.py:223` (collect to_persist list of pre-normalized fields/recipients/signals instead of immediate `_persist_match` inside per-msg/per-pk loop; call batch; move receipt into batch tx; added `persistence` + per-proj to `DiscoveryReport`/`ProjectMatchSummary`).
- `src/hb_assistant/construction/store/repositories.py:36` (new `EmailDiscoverBatchApplyError`), `5085` (batch method), `5300` area (inlined SQL for message/recip/match + receipt + crawl + sync inside one `with transaction`; `_persist_failed_receipt` best-effort sep tx; supports `failure_injector`).
- `src/hb_assistant/construction/store/__init__.py` (re-export error).
- `src/hb_assistant/cli/graph.py:2301` (discover_cmd: catch `EmailDiscoverBatchApplyError` to surface `diagnostic`; client close in finally already present; "ok" path unchanged).
- Calendar: `src/hb_assistant/construction/calendar/event_indexer.py:244` (after normalize: chunk event_records, loop calls to enhanced batch with `chunked`/`partial_ok`/`is_final_chunk`/`failure_diagnostics` list; accum indexed; status=`completed_with_errors` on per-ev diags; persisted accepts with_errors), `167` (status doc), module doc.
- `src/hb_assistant/construction/store/repositories.py:924` (enhanced `apply_calendar_index_batch`: new params `chunked,is_final_chunk,partial_ok,failure_diagnostics,last_event_ordinal`; per-ev `try` in loop when partial_ok (collect+continue, no rollback of goods); `INSERT OR IGNORE` for crawl_run + COALESCE accum for indexed on checkpoints; conditional 'checkpointed' vs 'completed'; sync updated every chunk; failed path unchanged).
- `src/hb_assistant/cli/graph.py:1896` (calendar_index_cmd: compute top-level "ok" as `not any hard-failed source` so partials (with_errors) still ok=True; richer diags in per-source results).

**Batching vs churn**: Mail all-project (many pilots) now 1 conn/tx for N matches (vs N*(1+recip+signals) before); receipt always safe. Calendar larger (max-items 100/200) now N/100 txs with intermediate checkpoints (crawl status=checkpointed, accum events_indexed, sync last_attempted) vs 1 giant tx; per-ev error isolation (diags like `{"event_ordinal":X, "event_index_id":hash, "operation":"event_upsert", "exception_type":...}` collected, other events in chunk succeed).

**Per-project / per-ev diags + checkpoints**: Mail `DiscoveryReport.persistence` + `ProjectMatchSummary.persistence` + per-project aggs; CLI surfaces batch diag on err. Calendar `IndexResult.failure_diagnostics` now populated with per-ordinal even on partial success; crawl_run rows show 'checkpointed' + partial counts between chunks; final 'completed'.

**Safe finalization + receipts**: Batch methods always finalize receipt (ok inside main tx; failed + crawl failed in sep tx on err). For calendar chunks, non-final update crawl to checkpointed (prior goods stay); final chunk does completed + sync.

**Preserved (no regression)**: project-scoped discover (`--project X` still early-filters descriptors in load_pilot...); bounded windows + max_items (calendarView never full); all in-memory preview match only; guardrails in reports (`full_body_persisted:false`, `join_url_persisted:false`, `mailbox_read_only:true`, `subject_matched_in_memory_only`); no raw in SQLite (CHECKs + normalize + guards); no M365 writeback (endpoint guards + no mutation methods); dry default + explicit --apply; idempotent (ON CONFLICT hashes); all paths outside MCP (direct `hb-assistant graph mail/calendar *`); no schema bump (reuse V23 crawl/sync + processing_receipt).

**Validation matrix (see verify-suite)**: mail status, scoped + all-project (bounded --max-messages) dry/apply; calendar bounded + larger --max-items dry/apply; ruff/mypy/compile; pytest on discovery/cli/indexer/status; construction-agent validate. No MCP commands used.

Cross-refs: 148 (batch tx), 21 (indexing), 04 (read models), 20 (mail/calendar), 00-README (07B ledger), 121 (truthful state), 08d (MCP outside).

(Changeset surgical; only reliability + diags in the two flows.)
