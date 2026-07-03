# N2 · 11 — Next-Phase Recommendation

## Recommendation: **N2B — Schema-Fix Closeout + Security-Gate Completion** (before any N3)

Choose N2B (not N3 yet) because the schema code fix is done but the **non-code gates remain open**:
auth/security ACL hardening, public-exposure confirmation, and the runtime-user/admin split are all
still WARN/OPEN from N1D. Those must clear before a copied DB (which may carry Text-Vault-referenced
rows) is ever placed on the NAS.

### N2B scope

1. **Land the N2 schema fix** (operator authorizes commit/push of this branch).
2. **Harden NAS auth/security ACLs** (operator via DSM File Station or approved sudo path); re-verify
   `ls -ld` no longer shows 0777.
3. **Confirm public exposure** (firewall/router/Tailscale Funnel/Serve) — operator answers the N1D
   exposure questions or an admin-run status check.
4. **Verify the bfetting control path** (SSH + sudo) before any demotion of `personal-assistant-svc`
   from `administrators`.
5. **Fix the pre-existing scaffold test** `test_nas_runtime_scaffold.py::test_dockerignore_excludes_config_db_and_secrets`
   to assert the narrowed secret-file patterns instead of `**/security/`/`**/auth/` (see `09`).
6. **Address the test-writes-tracked-file quirk** in `test_automation_executor_service.py` (see `09`).

## Then: **N3 — Safe Copied-DB Creation by SQLite Backup API**

Only after N2B clears every gate AND the operator explicitly authorizes a bounded copied-DB phase.
N3 executes `05` (backup-API copy) + `06` (quiesce) + `07` (copied-DB smoke) with rollback (`05`/`06`)
and secrets handled per `08`. **N3 is still not a production cutover.**

## Ordering invariant

`N2 (schema fix) → N2B (security gates + closeout) → N3 (copied-DB, backup-API) → … → production cutover`.
Copied-DB smoke and production cutover both remain **prohibited** until explicitly authorized at the
appropriate later gate.
