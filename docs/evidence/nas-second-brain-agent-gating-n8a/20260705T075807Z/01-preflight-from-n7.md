# 01 — N8A Preflight

**Phase:** N8A — Second-Brain Agent / Watchers / Scheduler Gating (live-proof closeout)
**Stamp:** `20260705T075807Z`
**Worktree:** `/Users/bobbyfetting/hb-pa-n8a-20260705T075807Z`
**Branch:** `ops/nas-second-brain-agent-gating-n8a-20260705T075807Z`
**Base:** `origin/main` @ `704f59c8` (PR #279 — "Merge … docs/nas-n8-live-proof04-05-20260704"). This base already carries the full N8 hardening **and** the N8 live proofs 04–07 (in `docs/evidence/nas-second-brain-agent-gating-n8/live-20260704/`).

> Filename retains the N8 convention `01-preflight-from-n7.md`; the actual preflight base for N8A is **N8 on `origin/main`**, not N7. Local `main` was 58 commits behind `origin/main`; N8A was branched from `origin/main`, never local `main`.

## A. Base reconciliation (STOP-condition cleared)

- `git fetch origin --prune` run; `origin/main` = `704f59c8`.
- Fresh worktree created off `origin/main`; `git status` clean; branch tracks `origin/main`; 0 ahead / 0 behind at creation.
- N8 live proofs 04–07 confirmed present and **PASS** on the base (`live-20260704/00-live-proof-index.md`: "All four N8 live NAS proofs (04–07) are complete and PASS"). N8A therefore performs **no re-proof** — it references these and closes the live-proof residue.

## B. Confirmed NAS runtime parameters (repo truth, non-secret)

Sourced from `deploy/nas/hb-pa-config.nas.example.yml`, `deploy/nas/compose.yaml`, `deploy/nas/mcp/hb-pa-config.mcp.example.yml`.

| Parameter | Value |
|---|---|
| NAS service root | `/volume2/personal-assistant` (NAS-local, not SMB/`/Volumes`) |
| App-support root (relocation seam) | `/volume2/personal-assistant/app-support` (`HB_PA_CONFIG` → `paths.application_support_root`, `config/loader.py:49` → `config/path_policy.py:57`) |
| DB path (derived) | `/volume2/personal-assistant/app-support/db/hb-personal-assistant.sqlite` |
| Locks dir (derived) | `/volume2/personal-assistant/app-support/locks` (`config/path_policy.py:94`) |
| Config files on NAS | `/volume2/personal-assistant/config/hb-pa-config.yml`, `…/hb-pa-config.mcp.yml` |
| Obsidian vault (backend scaffold sentinel) | `…/app-support/_vault_disabled` — **deliberately inert**; N8A must preserve this sentinel |
| Runtime user | `personal-assistant-svc` = uid `1028`, group `users` = `100` (`compose.yaml` `user: "1028:100"`); no direct SSH login |
| Control user | `bfetting` (SSH port `10021`, host alias `hb-nas`) |
| Tailnet exposure | loopback-only default (`HB_PUBLISH_ADDR=127.0.0.1`); tailnet IP redacted as `<nas-tailnet-ip>` in repo |
| Storage guard prefix | `NAS_VOLUME_PREFIX="/volume2/personal-assistant/"` (`config/db_storage_guard.py:15`) |

**Carried-open `/volume1` drift (to remediate in N8A live phase):** the live NAS config files still set `application_support_root` and the `obsidian_vault` sentinel under `/volume1` (N8 finding `06a`); a dead `/volume1/personal-assistant/bin/hb-mcp-runner` sudoers rule remains (`05a`).

## C. Mac-side posture (single-writer preflight — verified this session, read-only)

- **No** `uvicorn` / `analytics.api` / `hb-assistant scheduler run` / `second-brain` / `source-watch` process running. ✅
- **Port 8000 not listening.** ✅
- **launchd finding (single-writer):** `com.hb.personal-assistant.scheduler.production` is **loaded but not running** (`launchctl list` → column `-` = no PID, last exit `0`). Plist runs `/Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant scheduler … --environment production` daily at 20:00, writing the **Mac** app-support (`~/Library/Application Support/HB Personal Assistant/…`) — a **different DB from the NAS**. Per operator decision this is a **N8B/N9 cutover action item, not an N8A blocker** (N8A enables no NAS-side continuous jobs). **Not modified this session.** See `../live-20260705T075807Z/04-mac-scheduler-status.md`.
- `com.hbintel.*` launchd agents are a **different project** (HB Intel SPFx) — out of scope.

## D. Boundary posture

- No push. No broad source scan. No Cloudflare / public exposure. No new ingestion / card / re-proof.
- Any live NAS mutation (config-drift edit, dead-sudoers removal, proof-runner cleanup) is **per-step operator-approved**; RO live checks use existing repo tooling or a minimal exact-command runner (no broad `sqlite3`/shell/Python/Docker/wildcard-sudo).
- Direct SSH for `personal-assistant-svc` not restored; sudo stays password-required.

## E. Verdict

**PASS (preflight).** Clean base off `origin/main`, gating code intact (see `03`), Mac posture read-only and single-writer-safe for a non-live audit. Live cleanup steps proceed only under per-step approval.
