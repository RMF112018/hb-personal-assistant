# 24 — Phase 07B: Email Thread Summary Materialization

Phase 07B Prompt 07. Status: implemented at this record's commit.

## Problem

The V11 `email_thread_summaries` table, the V23 `email_thread_summary_materialization_runs`
audit table, the `EmailThreadSummaryPolicy` loader, and `ConstructionStore.upsert_email_thread_summary`
all existed, but nothing **materialized** thread summaries: there was no component to group
indexed email by `thread_key`, build a redacted summary, route sensitive threads to review,
and record an auditable run. `construction/email/thread_summary.py` did not exist.

## Change

New `EmailThreadSummaryMaterializer` (`construction/email/thread_summary.py`) plus supporting
store helpers and a CLI command. It is **local-only and Graph-free** — it reads local SQLite
rows (`email_messages`, `email_project_matches`, and, under the controlled body-context
policy, the local encrypted-body vault) and writes only local rows behind an explicit apply.

- **Discovery:** distinct `thread_key`s from the project's matched messages
  (`list_email_project_matches` → `get_email_message`), bounded by `max_threads`.
- **Aggregation (per thread):** `message_count`, first/last datetime, `conversation_id`, and
  participants as **hashed** sender addresses (`sender_address_hash`). The persisted
  `summary_redacted` is **metadata only** (the policy's `summary_mode` is `metadata_only`):
  counts, the time window, and detected review-category ids — no subject, preview, or body
  text. Capped at `policy.defaults.max_summary_chars`. `summary_policy='metadata_only'`,
  `model_used=None`, `model_output_validated=False`.
- **Controlled body-context policy:** only when the caller flag `use_encrypted_body_context`
  **and** `policy.defaults.allow_encrypted_body_context` are both true, each message body is
  decrypted in memory (`get_email_body_vault_ref` + `decrypt_text`) to improve review-category
  recall, then immediately `del`-eted. Decrypted plaintext is never added to the summary,
  logged, returned, or persisted.
- **Review routing:** `classify_review_categories` over the in-memory redacted subjects/previews
  (plus the decrypted scan when enabled); any hit, with the policy's `route_sensitive_to_review`
  / `route_high_impact_to_review`, sets `review_required=True` and enqueues an
  `email_review_queue` item against the thread's latest message (idempotent).
- **Audit:** a `email_thread_summary_materialization_runs` receipt is opened/closed with
  counts; its `raw_body_persisted` / `raw_prompt_persisted` / `raw_response_persisted` /
  `external_writeback_performed` CHECK columns are never written (defaults hold them at 0).
- **Posture:** `dry_run=True` is the default and persists nothing; `dry_run=False` applies.

### Store helpers (`construction/store/repositories.py`)
- `get_email_thread_summary(thread_key)` and `list_email_thread_summaries(*, project_key,
  review_required, limit)` (dict return; `participants_hash_json` decoded; bool flags as
  booleans).
- `insert_email_thread_summary_materialization_run` / `complete_email_thread_summary_materialization_run`
  (mirror the calendar crawl-run helpers; never write the guard CHECK columns).

### CLI
`graph mail thread-summary` (`cli/graph.py`, under the `graph mail` group) — `--project`,
`--lookback-days`, `--max-threads`, `--use-encrypted-body-context`, `--dry-run/--no-dry-run`
(default dry), `--json` — mirrors `graph mail classify`.

## Guardrail invariants
- No Microsoft 365 mutation/writeback; mailbox read-only; the materializer never calls Graph.
- The persisted summary is metadata-only; no raw subject, preview, body, prompt, or model
  response is persisted. Participants are hashes.
- Local writes only on `--no-dry-run`; dry-run is the default.
- Human review remains mandatory for sensitive/high-impact threads (enforced by routing).

## Evidence

`docs/evidence/construction-intelligence-phase-07b-calendar-email/07-email-thread-summary-proof.md`
(local validation + redacted live real-store proof). The no-writeback / no-raw-body prover
does not yet scan the V11/V23 email-thread or V14 classification tables — deferred to
Phase 07B Prompt 12.
