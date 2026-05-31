# 25 — Phase 07B: Meeting↔Email Relationship Candidates

Phase 07B Prompt 08. Status: implemented at this record's commit.

## Problem

The V23 `meeting_email_relationship_candidates` table and the JSON contract
(`meeting_email_relationship_candidate_contract.json`, `auto_promotion_allowed=false`) plus
its loader existed, but nothing **built** the candidates: no component paired indexed
calendar events with materialized email threads, scored corroborating signals, and persisted
confidence-labeled candidate rows.

## Change

New `MeetingEmailCandidateBuilder` in a new `construction/relationships/` package. It is
**local-only and Graph-free** — it reads the redacted calendar index, the email thread
summaries, and the email messages' (already openly persisted) `sender_domain` values, and
writes only local candidate rows behind an explicit apply. It **never auto-promotes**: every
row carries `promotion_status='candidate'`, `model_proposed=False`, and the calendar/thread
rows are never written.

### Signals (safe, computable)
- **time_window** — does the event `[start,end]` interval overlap the thread
  `[first_message,last_message]` span? `margin_hours` recorded; `within_window` = margin ≤
  `time_window_hours` (default 72).
- **organizer domain** — is the event `organizer_domain` among the thread messages'
  `sender_domain`s? (domain only — never a raw address; the persisted `participant_signal`
  stores only `{"organizer_domain_present": bool}`.)
- **subject topic** — not computable (thread summaries are metadata-only and expose no
  subject word-token hashes), so `subject_topic_signal` is left null.

### Scoring (temporal relevance required)
A shared domain alone is **not** sufficient — the GC emails its own domain constantly, so a
domain match must also be temporally relevant (this was confirmed against the real store,
where unconditional domain matching produced ~960 near-cartesian candidates vs. 75 once gated
by the time window):
- **strong (0.80)**: time overlap AND domain match (`time_and_domain`)
- **moderate (0.60)**: domain match AND within the time window, no overlap (`domain_and_time_window`)
- **weak (0.40)**: time overlap only, no domain match (`time_overlap`)

`review_required = confidence_class in {moderate, weak, model_proposed, sensitive}` (per
contract; strong is not auto review-required). Output is bounded by `max_candidates`
(default 1000).

### Persistence
- `source_reference_json` (NOT NULL) carries only ids/hashes/datetimes:
  `event_index_id`, `thread_key_hash`, event start/end, thread first/last message datetimes.
  `thread_key_hash = hash_value(thread_key)`; `candidate_id = hash_value(event|thread|type)`.
- Naive/aware stored timestamps are normalized to UTC-aware before comparison.

### Store / CLI
- `repositories.py`: `upsert_meeting_email_relationship_candidate` (INSERT … ON CONFLICT
  (candidate_id); never writes the raw_body/raw_prompt/raw_response/external_writeback CHECK
  columns), `list_meeting_email_relationship_candidates`; and `list_calendar_event_index`
  extended additively to return `start_datetime_utc`/`end_datetime_utc` (non-private).
- `graph calendar meeting-email-candidates` (`cli/graph.py`, under the calendar group,
  mirroring `project-match`): `--project`, `--source`, `--time-window-hours`,
  `--max-candidates`, `--dry-run/--apply` (default dry), `--json`.

## Guardrail invariants
- No Microsoft 365 mutation/writeback; builder is Graph-free; calendar + mailbox read-only.
- No raw subject, address, body, token, or URL in code, persisted rows, JSON, or evidence —
  hashes/bools/datetimes/counts only.
- Local writes only on `--apply`; dry-run is the default.
- No model-only auto-promotion: `promotion_status='candidate'`, `model_proposed=False`;
  moderate/weak route to human review.

## Evidence

`docs/evidence/construction-intelligence-phase-07b-calendar-email/08-meeting-email-candidate-proof.json`
(local validation + redacted live real-store proof). The no-writeback / no-raw-body prover
does not yet scan the V23 candidate or V11/V14 email tables — deferred to Phase 07B Prompt 12.
