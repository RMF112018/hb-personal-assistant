# 01 — Preflight

**Phase:** N4B NAS-local SQLite performance benchmark (evaluation only — no production cutover)

| Item | Value |
|---|---|
| Branch | `bench/nas-sqlite-n4b-20260704T072309Z` |
| Worktree | `/Users/bobbyfetting/hb-personal-assistant-worktrees/bench/nas-sqlite-n4b-20260704T072309Z` |
| HEAD | `39961a35` (base `ops/nas-copied-db-n3-20260704T060648Z`) |
| Evidence TS | `20260704T072309Z` |
| Benchmark-only | **Yes** — no backend, secrets, schedulers, or cutover |

## N3 inherited state

| Item | Value |
|---|---|
| N3 evidence | `docs/evidence/nas-copied-db-n3/20260704T060648Z/` |
| N3 verdict | **PASS** |
| N3 evidence committed | Yes (on N3 branch locally; not on `main`/remote) |
| N3 final DB path | `/volume1/personal-assistant/app-support/db/hb-personal-assistant.sqlite` |
| N3 schema / tables | schema **98**, **506** tables (N3 closeout) |

## N3 NAS DB preflight (read-only metadata)

SSH as `bfetting@<tailnet-host>:10021` (TheLakeHouseNAS):

```
-rw------- 1 personal-assistant-svc users 3.9G Jul  4 06:23 .../hb-personal-assistant.sqlite
Size: 4151631872  Inode: 3264  Uid: 1028(personal-assistant-svc)
```

- DB exists at expected path
- Owner `personal-assistant-svc:users`, mode `600`
- `bfetting` cannot read DB bytes (PermissionError) — expected least-privilege

## Sudo / svc-user note

Non-interactive `sudo -u personal-assistant-svc` requires a password in this session (`sudo -n` failed). NAS benchmarks ran on a scratch copy at the same `/volume1` btrfs path as `bfetting` (see `05-nas-copy-and-validation.md`). N3 final DB was not opened for write.

## Git status at preflight

Primary repo on `main`; N4B work in isolated worktree.

## Explicit boundary statement

This phase creates benchmark copies in scratch only, runs synthetic workloads, and produces evidence. It does **not** authorize N4 production startup, secrets migration, backend exposure, or cutover.
