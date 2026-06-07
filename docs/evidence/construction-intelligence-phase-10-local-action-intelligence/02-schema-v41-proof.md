# Phase 10 Prompt 02 — V41 Schema Status Proof

**Status:** ready · **generated_utc:** 2026-06-07T19:23:17.433288+00:00

- repo_sha: `cc879caf4c05d5948c3d454b2b7ca5e2e6de2753`
- schema_version: 41 (expected 41)
- tables present: True (21) · guards present: True (13/table) · guard_sum: 0

## Tables

| Table | Present | Guards | Rows | Guard sum |
| --- | --- | --- | --- | --- |
| local_model_profiles | True | True | 0 | 0 |
| local_model_status_receipts | True | True | 0 | 0 |
| local_model_run_receipts | True | True | 0 | 0 |
| ai_job_queue | True | True | 0 | 0 |
| ai_job_runs | True | True | 0 | 0 |
| task_candidates | True | True | 0 | 0 |
| commitment_candidates | True | True | 0 | 0 |
| candidate_source_refs | True | True | 0 | 0 |
| candidate_review_events | True | True | 0 | 0 |
| accepted_tasks | True | True | 0 | 0 |
| accepted_commitments | True | True | 0 | 0 |
| follow_up_watch_items | True | True | 0 | 0 |
| follow_up_status_events | True | True | 0 | 0 |
| phase10_relationship_candidates | True | True | 0 | 0 |
| daily_brief_action_candidates | True | True | 0 | 0 |
| obsidian_note_index | True | True | 0 | 0 |
| obsidian_note_tag_index | True | True | 0 | 0 |
| obsidian_managed_section_registry | True | True | 0 | 0 |
| obsidian_note_update_receipts | True | True | 0 | 0 |
| claude_context_packets | True | True | 0 | 0 |
| claude_context_packet_items | True | True | 0 | 0 |

## Guardrails

Additive-only (V1–V40 untouched, idempotent); every table carries the 13 `CHECK(=0)` guard columns; only redacted/hashed columns are stored (no raw body/payload/prompt/response/URL/token); dev/production isolation via `ai_job_queue.environment`. Read-only, advisory; never a determination.
