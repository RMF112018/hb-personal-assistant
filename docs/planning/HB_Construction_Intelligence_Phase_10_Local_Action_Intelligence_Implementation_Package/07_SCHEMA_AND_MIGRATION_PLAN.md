# 07 Schema and Migration Plan

## Migration principle

Additive only. Do not alter or drop existing tables. Every new table must include guard columns consistent with existing no-raw/no-writeback practice.

## Proposed schema version

Phase 10 should bump schema from V40 to V41 or current repo head + 1 after the local agent rebaselines.

## Table families

1. Local model runtime:
   - `local_model_profiles`
   - `local_model_status_receipts`
   - `local_model_run_receipts`

2. AI jobs:
   - `ai_job_queue`
   - `ai_job_runs`
   - `ai_job_steps`
   - `ai_job_output_receipts`

3. Action intelligence:
   - `task_candidates`
   - `commitment_candidates`
   - `accepted_tasks`
   - `accepted_commitments`
   - `follow_up_watch_items`
   - `follow_up_status_events`
   - `candidate_source_refs`
   - `candidate_review_events`
   - `suppression_rules`

4. Relationship intelligence:
   - `phase10_relationship_candidates`
   - `phase10_accepted_relationships`

5. Daily Brief:
   - `daily_brief_action_candidates`
   - `daily_brief_action_candidate_refs`

6. Obsidian:
   - `obsidian_note_index`
   - `obsidian_note_frontmatter_index`
   - `obsidian_note_tag_index`
   - `obsidian_note_link_index`
   - `obsidian_managed_section_registry`
   - `obsidian_note_update_receipts`
   - `obsidian_tag_suggestions`

7. MCP packets:
   - `claude_context_packets`
   - `claude_context_packet_items`
   - `mcp_resource_access_receipts`

See `resources/sql/phase_10_schema_additions.sql`.
