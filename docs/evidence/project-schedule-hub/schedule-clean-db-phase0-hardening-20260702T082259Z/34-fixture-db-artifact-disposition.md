# Fixture DB artifact disposition

## DB files found in evidence directory (before cleanup)

- `fixture-phase0.db`
- `fixture-preview.db`
- `fixture-preview.db-wal`
- `fixture-preview.db-shm`
- `fixture-purge-apply.db`
- `fixture-live-probe.db`

## Action taken

Moved to git-ignored location:

`local-sensitive/clean-db/phase0-evidence-fixtures/`

New purge apply proof regenerated at:

`local-sensitive/clean-db/phase0-evidence-fixtures/fixture-purge-apply-regen.db` (not committed)

Evidence directory `.gitignore` continues to exclude `*.db`, `*.db-wal`, `*.db-shm`.

## Proof: none tracked

```
git ls-files docs/evidence/project-schedule-hub/schedule-clean-db-phase0-hardening-20260702T082259Z/*.db
# (no output)
```

## Proof: none staged

Reconciliation commit uses explicit `git add` of JSON/Markdown/TXT only; no DB paths in staged set.

Committed evidence relies on JSON/Markdown/TXT proofs only.
