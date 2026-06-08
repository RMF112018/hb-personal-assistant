# 16 Rollback and Stop Conditions

## Stop immediately if

- Local repo truth materially differs from this package.
- The schema head is not V42 before migration and the difference is unexplained.
- Existing review commands would be broken by the proposed command names.
- `candidate_review_events` cannot be reconciled safely.
- Any review output requires raw body/prompt/response content.
- Any implementation path performs email/calendar/Graph/Procore/external writeback.
- Existing no-raw/no-writeback tests fail.
- Stable candidate IDs or source refs would need to be regenerated.

## Rollback guidance

If the migration is applied only locally and must be rolled back during development, restore from the dev DB backup/snapshot rather than trying to drop columns in SQLite.

```bash
cp "$DB" "/tmp/hb-personal-assistant-before-phase10a-review-v43.sqlite"
git status --short
git restore <changed-files>
```
