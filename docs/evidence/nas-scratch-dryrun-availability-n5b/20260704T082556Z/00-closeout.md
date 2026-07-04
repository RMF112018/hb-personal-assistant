# N5B — Scratch-Root Dry-Run / Availability Proof — Closeout

**Verdict: PASS.** (Upgraded from WARN after the `syn-work` read-only ACL follow-up — see `13`.)

> **Update 2026-07-04 (post-ACL):** A read-only ACL for `personal-assistant-svc` was assigned to `syn-work`
> (`/volume1/homes/bfetting/Work`) and verified: svc reads/traverses, and write attempts in `Work`, `NAS - HB`, and
> `Altman` are all **denied** with no leaked artifact (`13`). This was the sole remaining WARN driver, so N5B is
> upgraded **WARN → PASS**. The missing `ExternalSourceRoot.read_only` schema field is retained as a code-quality /
> future-activation hardening item (`05`/`11`) — **no longer** the active filesystem-control blocker. The
> first-indexing dry-run and DB-reconcile deferrals remain documented (`07`/`08`) and do not block PASS.

## What N5B did
1. Proved the NAS-mirrored vault and the NAS-native `syn-work` source root are reachable from a scratch runtime
   context — by `personal-assistant-svc`, read-only/stat-only — without touching production app-support, the production
   DB, active config, source registration, ingestion, card generation, watchers, or backend/MCP runtime.
2. Created a bounded scratch app-support root under `app-support-smoke/` (never production app-support).
3. Authored + validated non-active scratch configs pointing at the NAS vault + `syn-work` paths.
4. Ran the repo's read-only availability probe (stat-only) and confirmed it functions and corroborates the mirrored
   vault structure.

## Verdict basis (PASS)
All required proofs pass: NAS vault + `syn-work` reachable/readable by svc; scratch root created under
`app-support-smoke/` with no production/secret material; scratch + N5A configs validate non-active
(`enabled_roots=[]`); the stat-only availability probe runs clean; **and** `syn-work` read-only is now enforced at the
filesystem/ACL layer with a proven write-denial (`13`). Two deeper probes remain conservatively deferred (documented,
non-blocking):
- **Resolved (was the WARN driver):** `syn-work` read-only enforcement. A `personal-assistant-svc` ACL
  (`allow:r-x…:fd--`, no write/append/delete) now governs `/volume1/homes/bfetting/Work`; svc read passes and svc
  write is denied in `Work`, `NAS - HB`, `Altman` (`13`).
- **Retained as code-quality / hardening (not blocking):** `ExternalSourceRoot` has **no `read_only` field** (fields:
  `source_root_key, path, enabled, source_kind, sensitive`; `extra=forbid`); the planned `read_only=true` is
  documentary and dropped by the forward-compat loader (`05`). Filesystem/ACL now provides the actual read-only
  control; a schema-honored `read_only` (or `sensitive` handling) remains a future-activation hardening item.
- **First-indexing dry-run (12.B): deferred** — the tool refuses a `enabled=false` root by design
  (`obsidian_source_first_indexing_dryrun.py:132-133`) and an unmounted root (`:143`); the NAS path is not locally
  mounted and there is no repo checkout on the NAS. Non-blocking (`07`).
- **DB reconcile (12.C): deferred for safety** — read-only (`mode=ro`, fingerprint-guarded) but DB-backed; per §13 the
  production copied DB is not opened from this bounded phase. Non-blocking (`08`).

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
| **`syn-work` ACL read-only + write-denial** | ✅ svc ACL `r-x…` no-write; `WRITE_DENIED[Work/NAS - HB/Altman]=yes`; 0 leaks (`13`) |
| First-indexing dry-run | ⏸ deferred (design refusal + unmounted + no NAS checkout) — non-blocking |
| DB reconcile | ⏸ deferred for safety (production DB not opened) — non-blocking |

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
- `13-synwork-acl-write-denial-proof.md` — ACL + svc read + write-denial proof (the WARN→PASS upgrade).
- `drafts/` — non-active scratch configs.
- `local-sensitive/README.md` — un-redacted values (gitignored).
