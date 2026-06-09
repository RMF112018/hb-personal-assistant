# Acceptance Criteria

The relationship candidate engine is accepted only if:

1. It is implemented on the target branch with no unauthorized `main` changes.
2. It adds a first-class, dry-run-default CLI surface.
3. It persists only capped, idempotent, source-linked, reviewable relationship candidates.
4. It reuses deterministic relationship scoring; the model never decides relatedness.
5. It proves dry-run zero writes, apply requires cap, capped apply, idempotent re-run, and guard columns zero.
6. It has no external writeback of any kind.
7. It does not mutate email/calendar/Procore source tables.
8. It does not commit raw private data to repo, evidence, docs, tests, or logs.
9. It integrates with daily brief conservatively or clearly documents why integration was deferred.
10. Existing Phase 10 Checkpoint 1-current tests remain green except documented branch-independent failures.
11. `ruff`, format check, and `mypy` pass on changed scope.
12. Live workflow proof runs on a DB copy and produces useful, redacted operator output.
13. Docs and evidence describe behavior accurately.
14. Rollback is straightforward by reverting additive commits.

