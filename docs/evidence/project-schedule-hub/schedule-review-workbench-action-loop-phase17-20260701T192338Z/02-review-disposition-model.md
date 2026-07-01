# Phase 17 Review Disposition Model

## Canonical dispositions (stored in DB)

| Key | PM label | Operator selectable |
|-----|----------|---------------------|
| `needs_review` | Needs review | Yes |
| `accepted_for_follow_up` | Accepted for PM follow-up | Yes |
| `dismissed_not_material` | Dismissed as not material | Yes |
| `superseded` | Superseded | Yes |
| `duplicate` | Duplicate | Yes |
| `resolved` | Resolved | Yes |
| `blocked_by_identity` | Blocked by identity trust | **No** (system-gated) |
| `blocked_by_trust` | Blocked by analytics trust | **No** (system-gated) |

## Legacy aliases (read/write normalize, not stored)

- `open`, `watching` → `needs_review`
- `reviewed` → `accepted_for_follow_up`
- `dismissed` → `dismissed_not_material`

## Reason required (backend enforced)

`dismissed_not_material`, `superseded`, `duplicate`, `resolved` require non-empty `disposition_reason`.

## Trust gating

- System assigns `blocked_by_identity` / `blocked_by_trust` from trust read models on promote.
- Operators cannot select blocked dispositions from dropdown.
- Operators cannot move blocked items to `needs_review`, `accepted_for_follow_up`, or `resolved` while trust remains blocked.
