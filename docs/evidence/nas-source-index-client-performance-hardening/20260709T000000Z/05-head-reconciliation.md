# HEAD reconciliation

## Mismatch

| Source | Hash reported |
|--------|----------------|
| Completion summary (session) | `d8dfa5ee` as HEAD |
| Evidence `04-final-report.md` (before this closeout) | `6f54bdd017cdb51f6002322b6386f2752324e401` as final commit |

## Cause

Two local commits were created:

1. `6f54bdd0` — `feat(nas): source index health, query plan, default-on structure map`  
   (implementation + initial evidence; report was written pointing at this hash)
2. `d8dfa5ee` — `docs(evidence): record final commit hash for source-index hardening`  
   (only updated the evidence report text; became the new HEAD)

The report field "Final commit" was set to the **implementation** hash while HEAD advanced one docs-only commit. That is not a code/inventory drift; it is a documentation lag.

## Resolution (this closeout)

- **Authoritative final HEAD** for the branch tip before push/PR: see `05-final-head-and-inventory.md` (after any further closeout commits).
- `04-final-report.md` is updated to list:
  - **Implementation commit:** `6f54bdd0…`
  - **Docs evidence commit:** `d8dfa5ee…`
  - **Closeout HEAD:** current `git rev-parse HEAD` after this reconciliation commit
