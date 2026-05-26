# 07 — Source Link and Store Contract Specification

## Objective

Define the persistence and provenance contract for Phase 14 action intelligence and generated outputs.

## Source Link Principle

No generated work product should be persisted without traceability to its source records when a source is available.

## Existing Tables To Reuse

- `source_records`
- `emails`
- `calendar_events`
- `attachments`
- `files`
- `parser_outputs`
- `action_items`
- `source_links`
- `assistant_runs`
- `content_embeddings`

## New/Updated Store Helpers

Add helpers if missing:

```python
upsert_action_item(...)
get_action_item_by_stable_key(...)
list_open_action_items(...)
list_action_candidates_from_signals(...)
create_source_link(...)
link_action_to_sources(...)
record_generated_output_source_links(...)
```

## Action Upsert Behavior

- Upsert by `stable_key`.
- Preserve existing completed status unless explicitly reconciling stale/closed items.
- Update confidence upward when a stronger signal is found.
- Do not downgrade confidence unless a reconciliation command explicitly does so.
- Preserve user-completed state.

## Source Link Rules

| Link Type | Usage |
|---|---|
| `derived_from` | Generic generated-from relationship. |
| `mentions` | Bobby mention source. |
| `waiting_on` | Waiting-on signal. |
| `attaches` | Attachment/file relationship. |
| `parsed_from` | Parser output or generated text from file. |
| `written_to_note` | Generated output written to Obsidian. |
| `prepares_for` | Meeting prep linked to calendar event. |
| `semantic_match` | Retrieval hit relation. |

## Generated Output Source Linking

When a note is written or dry-run evidence is produced, the system should record or report:

- target note path or redacted path;
- source IDs used;
- action IDs used;
- link types;
- brief section references.

If dry-run mode is active, report `would_link` relationships without mutating.

## Migration Rules

- Prefer using existing schema before adding columns.
- If columns are needed, add idempotent migrations.
- Never use destructive migrations.
- Preserve existing local data.
- Provide tests for migration idempotency.

## Acceptance Criteria

- Every new persisted action is linked to at least one source record.
- Every generated note write can be traced to source IDs or explicitly says no source records were available.
- Existing completed actions are not reopened by repeated extraction.
- Store helpers are covered by tests.
