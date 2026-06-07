# 207. Phase 10 Local Action Intelligence — V41 Additive Schema

Date: 2026-06-07

Package: HB Construction Intelligence — Phase 10 Local Action Intelligence Implementation Package (Prompt 02)

## Decision

Migration **V41** adds the 21 Phase 10 persistence tables the Prompt 01 contracts describe. It is strictly additive — `CREATE TABLE IF NOT EXISTS` only, V1–V40 untouched, idempotent via the existing `schema_migrations` guard. No runtime consumes these tables yet (Prompts 03+); this prompt only lays the schema and a read-only status proof.

## Tables (21, by domain)

- **Local model runtime:** `local_model_profiles`, `local_model_status_receipts`, `local_model_run_receipts`
- **AI jobs:** `ai_job_queue`, `ai_job_runs`
- **Action candidates:** `task_candidates`, `commitment_candidates`, `candidate_source_refs`, `candidate_review_events`
- **Follow-ups:** `accepted_tasks`, `accepted_commitments`, `follow_up_watch_items`, `follow_up_status_events`
- **Relationships:** `phase10_relationship_candidates`
- **Daily brief:** `daily_brief_action_candidates`
- **Obsidian index:** `obsidian_note_index`, `obsidian_note_tag_index`, `obsidian_managed_section_registry`, `obsidian_note_update_receipts`
- **Claude / MCP packets:** `claude_context_packets`, `claude_context_packet_items`

## Guard convention

Every table carries the **13 Phase 10 guard columns** (`raw_email_body_persisted … calendar_mutation_performed`), each `INTEGER NOT NULL DEFAULT 0 CHECK(<col> = 0)`. In `migrator.py` the guard fragment is defined once (`_P10_GUARDS`) and interpolated into all 21 `CREATE TABLE` statements, so the guard set is identical by construction. These 13 columns exactly match the `guard_columns` lists in the Prompt 01 contracts — a parity test (`test_contract_guard_columns_match_schema`) ties the two prompts together. `obsidian_note_update_receipts` additionally enforces `changed_outside_managed_section = 0` and `mode IN ('dry_run','apply')`.

## Privacy & isolation

- **No raw columns.** All sensitive data is stored as `*_redacted` (titles, reasons, notes, paths, evidence) or `*_hash` (source refs, input/output context, note paths, packets, content). There is no raw body/payload/prompt/response/URL/token column anywhere in V41.
- **Environment isolation.** `ai_job_queue.environment` participates in `UNIQUE(environment, job_type, idempotency_key)`, keeping dev and production job queues isolated.
- **Provenance & review.** Candidate tables carry `confidence`, `model_profile_id`, `prompt_template_version`, `review_status` (default `pending`), `safety_category`, and a mandatory `candidate_source_refs` bridge (`source_ref_hash` + `source_family`), so an accepted task/commitment can never exist without source references.

## Indexes

The draft defined none; this migration adds seven additive `CREATE INDEX IF NOT EXISTS` supporting obvious later-prompt access paths: `ai_job_queue(environment,status)`, `task_candidates(review_status)`, `commitment_candidates(review_status)`, `candidate_source_refs(candidate_type,candidate_id)`, `follow_up_watch_items(watch_status,next_check_utc)`, `daily_brief_action_candidates(brief_date,section)`, `claude_context_packets(packet_type,packet_date)`.

## Proof surface

`build_phase_10_schema_status_report()` (CLI `second-brain phase-10 schema-status --json [--db <path>] [--write-evidence]`, in `construction/second_brain/local_ai/schema.py`) opens the DB read-only, fails closed if `schema_version < 41`, confirms all 21 tables + 13 guards per table, and sums the guard columns across all rows (must be 0). Read-only, advisory, never a determination; exits 0 when `ready`, 3 otherwise. Evidence: `docs/evidence/construction-intelligence-phase-10-local-action-intelligence/02-schema-v41-proof.{json,md}` (generated against a freshly-migrated temporary DB; the user's app DB is not mutated).

## Out of scope (later prompts)

Local model runtime/status population (Prompt 03), structured-output client (Prompt 04), job queue execution + run receipts (Prompt 05), extraction/classification writing candidate rows (Prompt 06+), Obsidian writer, MCP packet builder, and the frontend review queue.
