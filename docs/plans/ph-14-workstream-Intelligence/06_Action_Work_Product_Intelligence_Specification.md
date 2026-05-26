# 06 — Action / Work Product Intelligence Specification

## Objective

Define the deterministic action extraction system for Phase 14.

## Core Concepts

An **action item** is a source-linked local record representing something Bobby may need to do, monitor, review, prepare, or follow up on. It is not a Microsoft task and does not write back to Microsoft 365.

## Action Types

| Type | Meaning | Example Signal |
|---|---|---|
| `respond` | Bobby likely needs to reply. | “Can you respond...” |
| `review` | Bobby likely needs to review a file, decision, contract, or issue. | “Please review...” |
| `approve` | Bobby likely needs to approve or reject something. | “Need your approval...” |
| `follow_up` | Bobby should follow up with someone. | “Follow up with...” |
| `waiting_on` | Bobby is waiting on someone else. | “Waiting on John...” |
| `meeting_prep` | Preparation needed for a meeting. | upcoming calendar event + related source hits |
| `file_review` | A file needs review or ingestion. | eligible pending file candidate |
| `monitor` | Watch/track an unresolved item. | low confidence but persistent signal |

## Source Inputs

The extractor may consume:

- `emails` flags and redacted metadata;
- `body_match_excerpt_redacted`;
- `parser_outputs.text_excerpt`;
- `calendar_events` rows;
- `files` review queue;
- `retrieval` hits;
- `source_links` indicating `mentions`, `waiting_on`, `parsed_from`, `attaches`.

## Stable Key Rules

Each action must have a deterministic `stable_key` to prevent duplication. Recommended format:

```text
action:{action_type}:{primary_source_record_id}:{normalized_signal_hash}
```

Rules:

- Normalize whitespace and lowercase before hashing.
- Hash bounded redacted text only.
- Include primary source ID and action type.
- Do not include volatile timestamps unless the date is part of the action identity.

## Confidence Rules

| Confidence | Meaning |
|---:|---|
| `0.90+` | Explicit Bobby assignment or approval/review request. |
| `0.70–0.89` | Strong action phrase with Bobby mention or direct question. |
| `0.50–0.69` | Waiting-on/follow-up signal but weaker assignment. |
| `<0.50` | Monitor only; do not surface as priority unless repeated. |

## Redaction Rules

- Persist short redacted titles only.
- Persist bounded redacted excerpts only when needed for traceability.
- Do not persist raw email body text.
- Do not persist full file text.
- Do not include token/cache/secret strings in action content.

## CLI Commands

Target command group:

```bash
hb-assistant actions extract --dry-run --json
hb-assistant actions extract --json
hb-assistant actions list --json
hb-assistant actions reconcile --dry-run --json
```

`--dry-run` must not mutate the store.

## JSON Output Example

```json
{
  "command": "actions extract",
  "dry_run": true,
  "status": "ok",
  "candidates_seen": 12,
  "actions_would_create": 4,
  "actions_would_update": 2,
  "actions": [
    {
      "stable_key": "action:review:42:abc123",
      "action_type": "review",
      "title": "Review redacted source item",
      "confidence": 0.82,
      "source_record_ids": [42],
      "link_types": ["derived_from"]
    }
  ]
}
```

## Acceptance Criteria

- Repeated extraction does not duplicate records.
- Every persisted action has at least one source link.
- Dry-run reports planned changes without mutations.
- No full bodies or full files are persisted.
- Tests cover explicit action, weak monitor signal, waiting-on, duplicate prevention, and redaction.
