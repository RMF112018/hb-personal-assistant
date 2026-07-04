# N5B — Scratch-Root Dry-Run / Availability Proof — Closeout

**Verdict: WARN.**

## What N5B did
1. Proved the NAS-mirrored vault and the NAS-native `syn-work` source root are reachable from a scratch runtime
   context — by `personal-assistant-svc`, read-only/stat-only — without touching production app-support, the production
   DB, active config, source registration, ingestion, card generation, watchers, or backend/MCP runtime.
2. Created a bounded scratch app-support root under `app-support-smoke/` (never production app-support).
3. Authored + validated non-active scratch configs pointing at the NAS vault + `syn-work` paths.
4. Ran the repo's read-only availability probe (stat-only) and confirmed it functions and corroborates the mirrored
   vault structure.

## Why WARN (not PASS)
Everything *required* passed, but two conservative deferrals and one real schema finding hold this to WARN — exactly
the WARN profile defined in the runbook:
- **Schema finding (new):** `ExternalSourceRoot` has **no `read_only` field** (fields: `source_root_key, path,
  enabled, source_kind, sensitive`; `extra=forbid`). The planned `read_only=true` control is **documentary only** and
  is silently dropped by the forward-compat config loader. Since `/volume1/homes/bfetting/Work` is mode `777` (no FS
  enforcement), `syn-work` today has **neither** filesystem **nor** config-level read-only enforcement → activation
  stays blocked until a real read-only mechanism exists (schema `read_only`/`sensitive` handling, or perms/bind-mount).
  This is "config draft validation requires manual schema review later." → WARN.
- **First-indexing dry-run (12.B): deferred.** The tool refuses a `enabled=false` root by design
  (`obsidian_source_first_indexing_dryrun.py:132-133`) and refuses an unmounted root (`:143`); the NAS path is not
  locally mounted and there is no repo checkout on the NAS → infeasible to run meaningfully without activation. → WARN.
- **DB reconcile (12.C): deferred for safety.** The tool is read-only (`mode=ro`, fingerprint-guarded) but DB-backed;
  per §13, DB-backed checks with uncertainty are deferred rather than opening the production copied DB from this
  bounded phase. → WARN.

## Result summary
| Check | Result |
|---|---|
| NAS vault path exists / listable (bfetting metadata) | ✅ `221 files / 155 md` |
| Service-user vault read | ✅ `svc_vault_dir=yes`, `svc_vault_md_count=155` |
| `syn-work` path exists + top segments | ✅ `NAS - HB`, `Altman` present |
| Service-user `syn-work` bounded read | ✅ `svc_syn_work_top_segments=yes` |
| Scratch root under `app-support-smoke/` | ✅ `n5b-20260704T082556Z`, `drwx------ svc:users` |
| Scratch has NO production DB / key / .enc | ✅ `sqlite=0`, `key_or_enc=0` |
| Scratch configs (non-secret, non-active) | ✅ `2` files, `svc_can_read=yes` |
| Config draft validation (N5A + N5B) | ✅ parse + model_validate; `enabled_roots=[]` |
| Availability probe (stat-only, repo tool) | ✅ `read_probe_mode=stat_only`, 155 md candidates, 0 errors |
| First-indexing dry-run | ⏸ deferred (design refusal + unmounted + no NAS checkout) |
| DB reconcile | ⏸ deferred for safety (production DB not opened) |

## Boundaries held (see 09)
No production config activation · no source-root registration · no ingestion/card generation · no
backend/MCP/scheduler/watcher · no production DB writable open · no secrets/decrypted/note/source contents exposed ·
Mac vault untouched · NAS mirror untouched · `syn-work` untouched (not copied, not written) · nothing pushed.

## Evidence index
- `01-preflight-from-n5a.md` — git + N5/N5A PASS carry-forward.
- `02-nas-path-availability-proof.md` — non-sudo NAS metadata (vault + syn-work).
- `03-service-user-read-proof.md` — svc read of vault + syn-work + scratch config.
- `04-scratch-root-setup.md` — bounded scratch root creation + safety checks.
- `05-config-draft-validation.md` — parse/schema validation + the `read_only` schema finding.
- `06-availability-probe-results.md` — stat-only probe run + counts.
- `07-dry-run-results-or-deferred.md` — first-indexing dry-run deferral rationale.
- `08-db-safety-and-non-activation.md` — DB safety + reconcile deferral.
- `09-boundaries-maintained.md` — explicit non-actions.
- `10-rollback-plan.md` — scratch/evidence-only rollback.
- `11-n5c-n6-readiness.md` — what N5B unblocks + the read-only-enforcement gate.
- `12-git-status.md` — branch/HEAD/ahead + uncommitted posture.
- `drafts/` — non-active scratch configs.
- `local-sensitive/README.md` — un-redacted values (gitignored).
