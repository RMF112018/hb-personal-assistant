# Promotion Contract

Promotion converts candidate intent into an accepted local item.

## Requirements

- Explicit operator action only.
- Idempotent deterministic accepted ID.
- Accepted row inserted exactly once.
- Source refs preserved directly or indirectly.
- Project key preserved or `project_review_required` state retained.
- Redacted/bounded fields only.
- No external writeback.
- No raw content copy.

## Candidate routes

- `task_candidate` -> `accepted_tasks`
- `commitment_candidate` -> `accepted_commitments`
- `daily_brief_action` -> resolve matching domain candidate if possible; otherwise lifecycle-only accept with `promotion_skipped_unmapped`
- `follow_up_watch` -> managed watch disposition, not automatic new accepted row unless repo truth supports it

## Promotion status codes

- `promoted`
- `already_promoted`
- `promotion_skipped_unmapped`
- `promotion_blocked_source_missing`
- `promotion_blocked_project_review_required`
- `promotion_not_applicable`

