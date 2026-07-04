# 00 — N8 Closeout

**Phase:** N8 — Second-Brain Agent / Watchers / Scheduler Gating
**Stamp:** `20260704T154735Z` · **Branch:** `ops/nas-second-brain-agent-gating-n8-20260704T154735Z` (`c37af1bb`, +closeout)
**Verdict: PASS (code hardening + reconciliation) / HOLD (bounded live-NAS proofs 04–07).**

Bobby was away for the second half; work proceeded on best judgment strictly within non-live, non-push
bounds and stopped at the live-NAS boundary.

## Done (PASS)

1. **N3–N7 reconciliation** into 4 clean stacked branches off `origin/main` (28 commits): Cursor trailers
   stripped (0 attribution), 4 foundation dups + redundant viewer commit dropped, deploy/nas resolved to
   origin's hardened versions, 5 code commits **patch-id-identical** to originals, +1 honest test fix.
   Original branches preserved; **nothing pushed**. (`01`)
2. **Preflight** — reconciled base confirmed; NAS params (service root, app-support, DB, vault, source
   roots, runtime/control users) recorded; Mac backend/watchers/scheduler **not running**; single-writer
   launchd finding surfaced. (`01`)
3. **Inventory** — every worker/scheduler/watcher/drain/ingestion/automation/vault-write path + gate. (`02`)
4. **Hardening (Phase 3), temp-DB proven, `114 passed`:** (`03`)
   - **3a default-off** — `HB_NAS_RUNTIME=1` forces workers off + guards the on-demand watcher-route bypass.
   - **3b single-writer** — lease/lock host-stamped for cross-host attribution; fail-closed refusal proven.
   - **3c source identity** — `source_root_key` folded into `source_id` + composite unique index + **V99
     migration/backfill** across 8 FK'd tables (defer-FK, frozen formula). **Collision stop-condition
     cleared** for the code path.
5. **Audit/redaction** — receipts + row-count deltas; repo secret-scan has **0 N8-added findings**;
   0 attribution trailers. (`08`)
6. **Boundaries** (`09`) all held; **N8A readiness** assessed **NOT READY** (`10`); **git status** clean,
   unpushed (`11`).

## HOLD (require Bobby + live NAS)

- **04–07 bounded live proofs** (NAS test root, one ingestion, one card, duplicate-prevention incl.
  live-DB V99 backfill) — RUNBOOKS written; each needs per-step approval + on-NAS execution.
- **Single-writer cutover action item** — unload `com.hb.personal-assistant.scheduler.production` on the
  Mac before any NAS scheduler runs (not modified this session).
- **NAS firewall/router/Tailscale** reconfirmation (carried from N2C).

## Acceptance-criteria status

| Criterion | Status |
|---|---|
| Mac & NAS can't both run competing jobs unnoticed | **Met** within shared DB (host-stamped lease/lock + NAS default-off); residual different-DB risk bounded to the launchd action item |
| Workers/schedulers default-off unless deliberately enabled | **Met** (3a; NAS-authoritative) |
| Enabled job has ownership/lease/receipt/stop command | **Met** (lease+lock host-stamped, run registry, stop scripts) |
| NAS vault/source roots used intentionally | **Runbook** (04) — HOLD |
| Bounded ingestion/card proof succeeds | **HOLD** (05/06) |
| Duplicate prevention proven or blocker declared | **Met (temp-DB)**; live confirmation HOLD (07) |
| Destructive writes remain gated | **Met** (writes_enabled+markdown gate, SHA guard, dry-run defaults untouched) |
| Evidence contains no secrets | **Met** (08) |
| N8A readiness explicitly assessed | **Met** (10) |

## Residual risk / known pre-existing (NOT from N8)

- Live-DB V99 backfill on the NAS not yet run (temp-DB proven; frozen migration).
- Pre-existing (identical on the clean base): `test_phase_08b_schema_v30/v34` (FTS5 vs lifecycle
  contract), 2 automation-executor proof tests (delivery-pipeline/ollama-osascript), and repo
  sensitive-scan allowlist drift; `SIM103`/`F821` lint on untouched lines (`F821` = latent undefined
  `Path` in `build_db_diagnostics`, flagged not fixed).

## Note — stray-artifact cleanup (local history rewrite)

The 3b commit initially swept in 3 unrelated, test-regenerated phase-08b proof artifacts via `git add -A`.
History was rewritten to restore them to `origin/main` content; the N8 diff now touches only N8 files.
Pre-cleanup tip preserved as `backup/n8-preclean-20260704` until Bobby confirms. Details in `11`.

## Next step

Bobby reviews the reconciliation stack + the N8 diff, authorizes (a) push posture and (b) the live-NAS
bounded proofs 04–07 with per-step approval. **No push until then.**
