# 06 Candidate Review Domain Model

## Candidate identity

Candidate IDs are created during extraction and must remain stable. The review workflow must not regenerate candidate IDs or stable keys.

## Candidate types

Supported persisted types:

- `task`
- `commitment`

Unsupported extracted candidate types should remain non-persisted or explicitly skipped by the extractor. The review workflow should not invent storage for unsupported candidate types.

## Review statuses

Stored values:

- `pending`
- `accepted`
- `rejected`
- `snoozed`
- `suppressed`

User-facing alias:

- `ignored` maps to `suppressed`

## Mutable fields

Task candidates may permit correction of:

- `title_redacted`
- `project_key`
- `assignee_class`
- `due_at_utc`
- `urgency`
- `waiting_state`
- `safety_category`
- `reason_redacted`

Commitment candidates may permit correction of:

- `title_redacted`
- `project_key`
- `commitment_actor_class`
- `promised_at_utc`
- `due_at_utc`
- `urgency`
- `waiting_state`
- `safety_category`
- `reason_redacted`

## Immutable fields

The review workflow should not change:

- `candidate_id`
- `stable_key`
- `model_profile_id`
- `prompt_template_version`
- `created_utc`
- source refs
- guard columns
- any raw-content/writeback columns

## Audit event model

Every state transition or edit should write an append-only review event with:

- event ID
- candidate type
- candidate ID
- action
- prior status
- new status
- redacted note
- redacted changes JSON where applicable
- snooze-until time where applicable
- reviewer ref where available
- created timestamp
- guard columns remaining zero
