# Lifecycle State Contract

## Canonical states

- `new`: eligible newly surfaced item, not yet reviewed.
- `needs_review`: candidate needs operator review due to low confidence, unclear state, missing project, duplicate ambiguity, or source-quality concern.
- `accepted`: operator accepted candidate or accepted item is active/open.
- `rejected`: operator rejected candidate.
- `snoozed`: hidden until `effective_until_utc` / `snoozed_until_utc`.
- `merged`: source subject merged into canonical target.
- `closed`: handled/completed/resolved.
- `suppressed`: hidden recurring false positive or ignored item.
- `stale`: accepted/watch item aged or overdue with no resolution.
- `source_missing`: candidate lacks required source refs.
- `project_review_required`: project-like item lacks reliable project key.

## Precedence

When multiple states apply, use this precedence for default views:

1. `source_missing`
2. `merged`
3. `suppressed`
4. `rejected`
5. `snoozed` when return date is future
6. `closed`
7. `project_review_required`
8. `needs_review`
9. `stale`
10. `accepted`
11. `new`

Explicit `--include-hidden` views may show all states with reason codes.

## Task/commitment mapping

- `review_status=pending` -> `new` or `needs_review`
- `review_status=accepted` -> `accepted`
- `review_status=rejected` -> `rejected`
- `review_status=snoozed` -> `snoozed`
- `review_status=suppressed` -> `suppressed`

## Accepted mapping

- `status in completed/done/closed/resolved` or `completed_utc not null` -> `closed`
- overdue/stale threshold reached -> `stale`
- otherwise -> `accepted`

## Follow-up watch mapping

- `watch_status=closed` -> `closed`
- `watch_status=stale` -> `stale`
- quality/source-ref flags -> `needs_review` or `source_missing`
- otherwise -> `accepted`/monitoring state

## Daily-brief candidate mapping

- no source refs -> `source_missing`
- `project_key is null` for project-like item -> `project_review_required`
- lifecycle overlay event state if present
- otherwise `new`

