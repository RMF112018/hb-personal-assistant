# N2C-V · 05 — Service-User Least-Privilege Demotion (FINAL)

## Change
`personal-assistant-svc` was **removed from `administrators`**, leaving it a normal service account
scoped to the `users` group and the `http` group only.

## Operator machine proof
- Post-demotion identity: `uid=1028(personal-assistant-svc) gid=100(users) groups=100(users),1023(http)`
  — no `administrators` (101) membership.
- Direct SSH as `personal-assistant-svc`: **Permission denied** (expected — service account has no
  interactive login after demotion).

## Agent corroboration captured THIS phase (read-only)
```
ssh -p 10021 personal-assistant-svc@<nas-tailnet> id  →  Permission denied, please try again.
```
Confirms from the agent's own vantage that svc can no longer log in.

## Runtime write-proof preserved (via `sudo -u personal-assistant-svc`)
The demotion did **not** break runtime file access. Write-proof PASS on all 9 runtime folders:
`auth`, `security`, `db`, `backups`, `logs`, `evidence`, `cache`, `tmp`, `runtime`
(owned/writable by svc; exercised through `bfetting` → `sudo -u personal-assistant-svc`).

## Net effect
Least privilege achieved: the account the future backend runs as can write only its own runtime
tree and cannot administer the NAS or log in interactively — while the human `bfetting` path (`04`)
retains full admin control.

**Gate: PASS.**
