# 12 — Git Status

## At N5B finalize
- Branch: `ops/nas-copied-db-n3-20260704T060648Z`
- HEAD: `2000e609` — `docs(nas): add N5A vault mirror config draft evidence`
- Ahead of `origin/main`: **9** (N3 → N4 → N4A → N5 → N5A; N5B not yet committed)
- Working tree: this N5B evidence directory is **untracked / uncommitted**:
  ```
  ?? docs/evidence/nas-scratch-dryrun-availability-n5b/
  ```

## Commit chain (local only, never pushed)
```
2000e609 docs(nas): add N5A vault mirror config draft evidence
caf719d8 docs(nas): add N5 vault source roots planning evidence
58d09f50 docs(nas): add N4A text vault copy evidence
39961a35 docs(nas): add N4 secrets auth text vault evidence
761864ea docs(nas): add N3 copied DB smoke evidence
```

## Posture
Evidence written and **left uncommitted**. Commit locally only on separate explicit authorization (proposed message
`docs(nas): add N5B scratch dryrun availability evidence`; markdown + `drafts/` only, excluding `local-sensitive/`).
Never push; no PR.
