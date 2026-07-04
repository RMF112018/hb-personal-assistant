# 12 — Git Status

## At N5A finalize
- Branch: `ops/nas-copied-db-n3-20260704T060648Z`
- HEAD: `caf719d8` — `docs(nas): add N5 vault source roots planning evidence`
- Ahead of `origin/main`: **8** (N3 → N4 → N4A → N5; N5A not yet committed)
- Working tree: this N5A evidence directory is **untracked / uncommitted**:
  ```
  ?? docs/evidence/nas-vault-mirror-config-draft-n5a/
  ```

## Commit chain (local only, never pushed)
```
caf719d8 docs(nas): add N5 vault source roots planning evidence
58d09f50 docs(nas): add N4A text vault copy evidence
39961a35 docs(nas): add N4 secrets auth text vault evidence
761864ea docs(nas): add N3 copied db evidence   (earlier in the stack)
```

## Posture
Evidence is written and **left uncommitted**. Per the N5A runbook, commit locally only on separate explicit
authorization (proposed message `docs(nas): add N5A vault mirror config draft evidence`; markdown + drafts only,
excluding `local-sensitive/`). Never push; no PR.
