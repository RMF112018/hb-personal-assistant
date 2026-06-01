# 53 — Phase 07D: Review-Controlled Correspondence Context

**Status:** Implemented (Phase 07D Prompt 10). **Read-only projection — no schema change, no V25
table, no persistence.**
**Scope:** Tie email thread summaries to the records they relate to — meetings, RFIs, submittals,
changes, commitments, daily-log issues, inspections, and documents — **only where relationships
already exist** in the cross-source substrate, via a new read-only `construction-agent correspondence
context/status` sub-app that extends the existing `construction/correspondence/` module.

## Problem

The substrate already carries email↔meeting and email↔record edges, but nothing presents them as
per-thread *correspondence context*. There is no dedicated V25 table for it (the 10 V25 tables don't
include one), and the existing correspondence module is read-only/advisory. This prompt projects the
existing edges onto each email thread.

## Design

### Engine — `construction/correspondence/correspondence_context.py`

`CorrespondenceContextBuilder(store)` is a read-only projection that persists nothing.
`context(*, project_filter=None, lookback_days=None, max_per_category=25, now_utc=None)` returns
`{command, ok, schema_version, project_filter, lookback_days, summary{threads_total, threads_linked,
project_confirmations, review_required_threads, by_category}, threads:[{thread_key, project_key,
message_count, last_activity, summary_redacted, review_required, project_confirmed, by_category,
related{category:[{ref, relationship_type, confidence_class, review_required, evidence_trail_id}]}}],
guardrails}`. `correspondence_context_status()` returns the summary block only.

**Anchor = `email_thread_summaries`.** Per thread:
- **Meetings** from `meeting_email_relationship_candidates`, matched on
  `thread_key_hash == hash_value(thread_key)` (the same hashing the substrate uses).
- **Records** from the email-source `cross_source_relationship_candidates` (`source_family=='email'`),
  rolled up message→thread via a `{message_id → thread_key}` map built from `list_email_messages`
  (only message_id/thread_key are read — never web_link/body). Each target is classified by
  `_categorize(target_family, target_record_type, relationship_type)` into one of the 8 categories;
  `project_match` is surfaced as a separate `project_confirmed` flag (not a record category).
- A thread is *linked* only if it has ≥1 meeting/record tie ("where relationships exist"); unlinked
  threads are counted in `threads_total` but omitted from `threads`.
- `lookback_days` (optional) filters on `last_message_datetime` against `now_utc`
  (default `datetime.now`, injectable for tests); when unset, output is fully deterministic.

**Review-controlled.** A thread/tie is `review_required` if any contributing edge is review-required,
weak, model-proposed, or sensitive_high_impact. Nothing is promoted (read-only).

### CLI — `construction-agent correspondence`

`context` (`--project`, `--lookback-days`, `--json`) and `status` (`--project`, `--json`). **No
`--apply`** — read-only.

### Not changed / reused

No store or schema changes; reuses `list_email_thread_summaries`, `list_email_messages`,
`list_meeting_email_relationship_candidates`, `list_cross_source_relationship_candidates`, and
`hash_value`. The existing `CorrespondenceReviewBuilder` is untouched (additive sibling module +
`__init__` export). Table inventory stays 120.

## Guardrails

Local-first, read-only against external systems **and** local SQLite (zero writes). Output carries
only the bounded `summary_redacted` (metadata-only by policy), counts, local record refs / hashes /
endpoint names, confidence classes, and evidence-trail ids — never a raw email body, subject, web
link, signed/download URL, token, secret, or financial amount (no-raw-content regex test). Advisory
only — no determinations; weak/model/sensitive ties stay review-required and are never auto-promoted.

## Validation

ruff / `mypy src` (187 files) / compileall clean; pytest **+6 new tests**. Live `correspondence
context --json` tied `tropical` email threads to their related records/meetings (read-only);
`correspondence status` mirrors the summary. Both no-writeback proofs pass; `table-inventory`
25 / 120 (no new table); `meeting_prep_readiness_claim=ready` unchanged.

## Files

- `src/hb_assistant/construction/correspondence/correspondence_context.py` (new); `__init__.py` (additive export).
- `src/hb_assistant/cli/construction.py` (`correspondence` sub-app).
- `tests/test_correspondence_context.py` (new).

See `docs/evidence/construction-intelligence-phase-07d-cross-source-meeting-prep/10-review-controlled-correspondence-context.md`.
