# 09 — Git Status

## Pre-commit
- Branch: `ops/nas-copied-db-n3-20260704T060648Z` (local only, never pushed).
- HEAD before N5C-B: `cbf2cea6` (`docs(nas): add N5C-A MSAL Graph auth proof`).
- Ahead of `origin/main`: **15** commits (all local; no push, no PR).
- Working tree before commit: only untracked `docs/evidence/nas-graph-me-smoke-n5c-b/` (this evidence package).

## Commit posture
- Stage **markdown only**: `git add docs/evidence/nas-graph-me-smoke-n5c-b/20260704T101826Z/*.md`.
- `local-sensitive/` is gitignored (`.gitignore` `docs/evidence/**/local-sensitive/`) — never staged.
- Message: `docs(nas): add N5C-B Graph me smoke evidence`.
- **No push. No PR.** Stop after the local commit.
