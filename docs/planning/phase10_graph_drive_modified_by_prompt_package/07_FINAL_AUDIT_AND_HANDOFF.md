# 07 — Final Audit and Handoff

## Objective

Conduct a final repo-truth audit of the modified-by metadata implementation and provide a concise handoff.

Do not modify code unless a safety/correctness defect is found and Bobby approves a fix.

## Audit checklist

Verify:

1. branch/HEAD/tree clean;
2. no unintended main changes;
3. schema migration present;
4. fresh DB migration works;
5. existing DB migration works;
6. canonical drive item table has required fields;
7. normalizer maps Graph `lastModifiedBy`;
8. indexer/upsert persists fields;
9. project reference still captured;
10. folder/path still captured;
11. file name still captured;
12. modified date/time still captured;
13. modified-by display name captured when Graph supplies it;
14. modified-by user ID/email/application captured per design;
15. missing data handled gracefully;
16. no Graph writeback;
17. no raw private values in committed docs/evidence/tests;
18. targeted tests green;
19. ruff/format/mypy clean;
20. live DB-copy proof complete.

## Required final response

Provide:

1. final branch;
2. final HEAD;
3. changed files;
4. schema version/migration;
5. tables/columns changed;
6. exact Graph fields now captured;
7. backfill/reindex instructions;
8. validation commands/results;
9. safe live coverage summary;
10. known limitations;
11. rollback instructions;
12. recommendation: ready for audit / needs fix / blocked.

## Commit behavior

If this prompt creates only a final chat handoff, no commit is required.

If it creates a repo evidence document, commit docs/evidence only.

Suggested commit message:

```text
docs(graph-files): final modified-by metadata handoff
```
