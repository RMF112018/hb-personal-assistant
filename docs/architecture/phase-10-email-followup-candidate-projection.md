# Phase 10 — Email Follow-Up Candidate Projection

**Status:** Active (this slice). **Scope:** convert the V49 *structured* email/thread substrate into
deterministic, source-linked, project-aware daily-brief follow-up / task / commitment candidates.

## Why

PR 23 landed the first daily-brief projection slice: an `email_calendar_projection` stage projects
V49 raw email/calendar into structured read models, and an honest *email/follow-up data-gap card*
appears when structured email exists but the follow-up/task/commitment layers are empty
(`email_followup_readiness.classify_email_followup_data_gap`). This slice fills that gap with a
deterministic extractor — replacing the card with real content when eligible candidates exist and
preserving it honestly when none are produced.

## Design

New module `construction/second_brain/local_ai/email_followup_candidate_projection.py`:

- **Structured-first, metadata-only.** Reads only safe structured fields from
  `email_raw_message_structured` / `email_raw_thread_structured` via
  `store.list_email_message_structured` / `list_thread_structured` — bounded subject, sender
  name/address/domain, sent/received timestamps, recipient/attachment/message/participant counts,
  body *availability flags* (never body text), `project_key`, `thread_ref`, `message_id_hash`,
  `source_quality`. Raw bodies are **never** loaded (`raw_access_used == False` always);
  `load_body(...)` remains the audited exceptional path for a deliberate future pass.
- **Deterministic.** No clock (`now_utc` is injected), no model, no randomness. Classification reuses
  the existing `score_email_task_signals(...)` scorer over a bounded subject-derived summary; family
  confidence is a deterministic per-family base plus a bounded per-signal increment.
- **Seven families** → daily-brief sections: `waiting_on_response`→`waiting`,
  `response_needed`/`stale_thread_nudge`/`time_sensitive_followup`→`follow_up`,
  `user_commitment`/`project_action_item`→`actions`, `third_party_commitment`→`waiting`.
  A first-person *promise* is a commitment; an *ask awaiting reply* is waiting/response — kept
  distinct so routine sent mail (no promise, no ask) never becomes a follow-up.
- **Sender direction** is resolved from an explicit/​env-driven `OwnerIdentity`
  (`HB_ASSISTANT_OWNER_ADDRESSES` / `HB_ASSISTANT_OWNER_DOMAINS`). When unknown, direction-dependent
  families (commitments, response/waiting) degrade honestly and are suppressed rather than guessed.
- **Honest project keys.** Resolution reuses `project_aliases.resolve_project`; a
  project-like-but-unresolved candidate is `review_required` with `project_key = None`. Keys are
  never invented.
- **Raw-safe output.** Titles/reasons are scrubbed of URLs, email addresses, and bearer-token-looking
  strings, then truncated (title ≤120, reason ≤240, next-action ≤160).

## Persistence (no schema change)

Existing idempotent tables cover the slice, so **no migration** was added:

- Domain rows: `upsert_task_candidate` (non-commitment families) / `upsert_commitment_candidate`
  (commitments) keyed by deterministic `candidate_id` + `stable_key`. These flip the data-gap card to
  *populated* (the readiness counts include `task_candidates`/`commitment_candidates`).
- Daily-brief rows go through the central `persist_candidate_with_refs(...)` → hashed
  `candidate_source_refs` for every row (100% coverage by construction).
- `follow_up_watch_items` is intentionally **not** written here — it is the post-acceptance monitor
  keyed to `accepted_*` rows (`follow_up_watch.run_follow_up_watch_scan`), not a projection target.

## Pipeline + gates

- `pipeline.py`: `email_followup_projection` is a generation stage inserted immediately after
  `email_calendar_projection`. It reuses the existing dispatch (per-stage cap, idempotency,
  receipt, `brief_freshness`).
- `daily_run.py`: the stage receipt extends `stage_context["email_followup"]` with
  `candidate_count`, `project_key_coverage`, `review_required_count`, `raw_access_count`, `degraded`.
- `usefulness_gate.py`: new contradictions (backward-compatible when context absent) —
  `email_followup_stage_degraded`, `email_followup_project_coverage_low_no_review`,
  `email_followup_raw_access_unaudited`. Missing source refs are already caught by the global
  `executive_source_ref_coverage_below_100` (the new families map to executive sections).

## Honest limitation

Subject-only metadata is sparse: commitments and explicit asks usually live in the message body, so a
real-mailbox snapshot yields mostly `time_sensitive_followup` candidates from the subject line. The
unit suite proves all seven families on crafted structured fixtures; surfacing body-derived families
is a deliberate, audited future pass (`load_body` + `raw_content_access_events`).
