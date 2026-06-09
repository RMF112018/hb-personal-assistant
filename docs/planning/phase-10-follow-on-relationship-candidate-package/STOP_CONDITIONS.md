# Stop Conditions

Stop immediately and report if any of the following occur:

## Branch / Git

- Current branch is not `experiment/local-agent-family-proof` and cannot be safely corrected.
- Working tree contains unrelated uncommitted user work that would be overwritten.
- `main` would be modified or merged without explicit Bobby authorization.

## Scope Conflict

- Daily pipeline pilot files are actively modified locally and this package would conflict.
- The repo already has a complete relationship-candidate workflow satisfying the acceptance criteria.
- The implementation requires reworking scheduler/browser/Obsidian delivery work already in progress.

## Data / Schema

- `phase10_relationship_candidates` or equivalent table is absent and a migration would be required without approval.
- Required source tables are empty or unavailable in the DB copy, making live proof impossible.
- Source refs cannot be resolved or persisted safely.

## Safety

- Any path would commit raw email, calendar, Procore, document, prompt, response, URL, token, or unsafe HTML.
- Any guard column becomes nonzero.
- Any source table mutates unexpectedly.
- Any external writeback is attempted.
- Any production DB mutation would occur without explicit approval.

## Quality

- Tests only pass by weakening guardrails.
- Relationship determination depends on local-model judgment instead of deterministic scoring.
- Daily brief enrichment becomes unbounded or noisy.
- Pipeline regression fails due to introduced code and cannot be fixed within scope.

