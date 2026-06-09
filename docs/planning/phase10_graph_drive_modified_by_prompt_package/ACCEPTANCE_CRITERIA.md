# Acceptance Criteria

The implementation is acceptable only when:

1. Modified-by metadata from Graph drive items is captured when available.
2. Modified-by display name is stored as raw local operational metadata.
3. Modified-by user ID is stored when available.
4. Modified-by email/UPN is stored if available and intentionally allowed by design.
5. Modified-by application display name is stored when available.
6. Raw `lastModifiedBy` JSON or equivalent is stored if the design requires it.
7. File name remains captured.
8. Folder/path remains captured.
9. Project/source reference remains captured.
10. Modified date/time remains captured.
11. Missing/malformed `lastModifiedBy` does not break indexing.
12. Existing DBs migrate cleanly.
13. Fresh DBs create the columns.
14. Re-indexing is idempotent.
15. Live DB-copy proof shows safe coverage counts.
16. No raw private file/user values are committed to the repo.
17. No Graph writeback is introduced.
18. Targeted tests pass.
19. ruff/format/mypy pass on changed modules.
20. Final handoff documents exact fields and limitations.
