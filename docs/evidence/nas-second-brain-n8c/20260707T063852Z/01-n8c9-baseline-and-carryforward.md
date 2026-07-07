# 01 — N8C-9 Baseline & Carry-Forward

## N8C-9 finalized and committed (Part 1)

N8C-9 (unified review overlay: queue + append-only disposition ledger + computed effective review state,
V105) was verified and committed locally on the prior cycle:

```
commit e218746a  feat(nas): add n8c review queue   (no AI trailer, not pushed)
parent 208e7b68  feat(nas): add n8c decision memory layer   (N8C-8)
```

- Committed with an explicit staged-file set (no blind `git add -A`); `local-sensitive/` stayed unstaged
  (git-ignored). No push, no PR, no merge.
- `LATEST_SCHEMA_VERSION` was 105 at N8C-9.

## Carry-forward into N8C-10

N8C-10 **consumes** the N8C-9 layer read-only; it does not duplicate or modify it.

| N8C-9 primitive | How N8C-10 uses it |
|---|---|
| `review_builder.discover_review_candidates(ReviewProviders, pack_id, kinds, limit)` | read-only, pack-scoped enumeration of anchored review drafts |
| `review_repository.get_effective_state(review_item_id)` → `{effective_review_state, effective_state, disposed, latest_disposition_id}` | resolves each draft's effective state (latest disposition else built default `candidate`) |
| `assistant_review_items` / `assistant_review_dispositions` / `assistant_review_events` | READ only; snapshot-proven unchanged across preview / dry-run / apply (see 08) |
| `context_pack_models.estimate_tokens` / char budgeting | mirrored by `ProjectionBudget` for token estimates |

**Discrepancy noted (unchanged from N8C-9):** the prompt's regression list referenced
`tests/test_review_disposition.py`, which does not exist — N8C-9 folded disposition coverage into
`test_review_repository.py` + `test_fastapi_analytics_review.py` + `test_nas_mcp_review.py`. The N8C-10
regression run uses the actual review test files (see 11).

## Base verification (read-only, this run)

```
$ git rev-parse HEAD
e218746afc97ce742801ace5d7acbbdf80c579c5
$ git merge-base --is-ancestor e218746a HEAD && echo YES
YES                         # N8C-10 branch is based on the N8C-9 commit
$ git log --oneline -1 e218746a
e218746a feat(nas): add n8c review queue
$ test ! -d src/hb_assistant/agent_bridge && echo ABSENT
ABSENT                      # no N8D / agent_bridge in this worktree
```
