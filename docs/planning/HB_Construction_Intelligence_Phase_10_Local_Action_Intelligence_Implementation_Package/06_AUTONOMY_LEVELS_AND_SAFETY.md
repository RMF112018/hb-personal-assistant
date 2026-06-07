# 06 Autonomy Levels and Safety

## Phase 10 permitted levels

- Level 0: model creates candidates.
- Level 1: user accepts/rejects/edits.
- Level 2: app updates local dashboards, local status, Daily Brief queues, and Obsidian marker blocks.
- Level 3: app drafts text/suggestions for user approval.

## Excluded level

Level 4 external action is rejected for Phase 10.

## Policy gates

Every Phase 10 run must emit guardrails:

```json
{
  "no_graph_writeback": true,
  "no_procore_writeback": true,
  "no_email_send": true,
  "no_calendar_mutation": true,
  "no_raw_content_persisted": true,
  "no_raw_prompt_or_response_persisted": true,
  "structured_output_schema_validated": true,
  "external_action_requires_approval": true
}
```

## High-stakes routing

Any item with `safety_category` in `contract`, `legal`, `financial`, `payment`, `claim`, `entitlement`, `schedule`, or `safety` must be:

- review required;
- displayed as a signal;
- excluded from auto-accept;
- excluded from model-generated final determinations.
