# Recommended AEOS Goal States

The repository's approved goal package may use a different vocabulary. Map
explicitly rather than silently renaming states.

1. `GOVERNANCE_INITIALIZATION`
2. `REPOSITORY_TRUTH`
3. `ARCHITECTURE`
4. `IMPLEMENTATION_PLANNING`
5. `PLAN_EXTERNAL_REVIEW`
6. `IMPLEMENTATION`
7. `IMPLEMENTATION_EXTERNAL_AUDIT`
8. `CORRECTIVE_IMPLEMENTATION`
9. `CORRECTIVE_EXTERNAL_AUDIT`
10. `MERGE_READINESS`
11. `MERGE_AUTHORIZATION`
12. `MERGED_PENDING_CLEANUP`
13. `POST_MERGE_VALIDATION`
14. `BRANCH_WORKTREE_CLOSEOUT`
15. `BOUNDED_CLOSURE_ASSESSMENT`
16. `CLOSED`

Recommended state statuses:

- `NOT_STARTED`
- `IN_PROGRESS`
- `READY_FOR_REVIEW`
- `REVIEW_BLOCKED`
- `BLOCKED`
- `COMPLETE`
- `CLEANUP_AUTHORIZED`
- `RETAINED`
- `CLEANUP_BLOCKED`
- `CLOSED`

Only operator authorization activates the next state. Merge must transition to
`MERGED_PENDING_CLEANUP`; it must not transition directly to `CLOSED`.
Post-merge validation and a cleanup, retention, or blocker receipt are required
before closure.
