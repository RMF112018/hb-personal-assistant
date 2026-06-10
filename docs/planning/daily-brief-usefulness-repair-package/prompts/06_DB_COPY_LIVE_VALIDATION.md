# Prompt 06 — DB-Copy Live Validation and Evidence

## Objective

Prove the repair on a production DB copy, with outputs confined to `/tmp`, and no production DB mutation.

## Required Actions

1. Run compile/tests.
2. Run DB-copy live proof using `validation/VALIDATION_COMMANDS.md`.
3. Capture DB integrity/quick check, production before/after hashes, daily-run JSON, latest status JSON, safe output paths, row counts/metrics, forbidden scan, and guard-column proof if relevant.
4. Inspect generated brief privately under `/tmp`.
5. Produce safe repo evidence under `docs/evidence/daily-brief-usefulness-repair/06-db-copy-live-proof/`.

## Expected Result

The copied-DB daily-run should either produce a useful, source-linked, project-resolved brief with nonempty deterministic sections or return degraded/partial with exact usefulness-gate failure reasons. A false `success` is failure.

## Suggested Commit

`test(second-brain): prove daily brief usefulness repair on DB copy`
