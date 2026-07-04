# 01 — N8 Preflight (from reconciled N7)

Phase: **N8 — Second-Brain Agent / Watchers / Scheduler Gating**
Stamp: `20260704T154735Z`
Worktree: `/Users/bobbyfetting/hb-pa-n8`
Branch: `ops/nas-second-brain-agent-gating-n8-20260704T154735Z`
Base: `recon/nas-code-n7` (`0c31429c`) — the reconciled N7 runtime, rebased on `origin/main` (`e3d57110`).

## A. N3–N7 prerequisite reconciliation (STOP-condition cleared)

Preflight found N3–N7 **local-only and unpushed**; `origin/main` carried only the N0–N2b foundation (PRs #270–273). Per Bobby's decision, N3–N7 were reconciled into a clean, attribution-free stacked-branch set off current `origin/main` **before** any N8 code:

| Branch | Tip | Content |
|---|---|---|
| `recon/nas-evidence-n2c-n4c` | `a6759965` | N2C–PR-C evidence (docs-only) |
| `recon/nas-evidence-n5` | `0a22b91c` | N5/N5A/N5B/N5C evidence (docs-only) |
| `recon/nas-code-n7` | `0c31429c` | **N7 runtime code** (MCP SSH launcher, FS roots, Obsidian write parity) + 1 test fix |
| `recon/nas-evidence-n7` | `c113e8e5` | N7 proof evidence (docs-only) |

- Dropped as already-on-origin / redundant: `581ad598`, `4fe34348`, `9bcf7e2e` (patch-identical), `b912b4ed` (diverged v98 → origin wins), `e862cc11` (viewer-lifecycle twin; 12/13 files byte-identical to origin, its `health.sh` older/word-split — origin's is hardened).
- All 16 `Co-authored-by: Cursor` trailers stripped → **0 attribution lines** in the stack. No Claude/Anthropic anywhere.
- All 5 reconciled N7 code commits are **patch-id-identical** to originals.
- Reconciled NAS suite **green (64 passed)**; obsidian mutation + pm-grade source-card tests **green (24 passed)**.
- Original branches preserved (tags `recon-src/n3-af482711`, `recon-src/n7-30252621`); **nothing pushed**.

## B. Confirmed NAS runtime parameters (repo truth, non-secret)

Sourced from `deploy/nas/hb-pa-config.nas.example.yml`, `deploy/nas/compose.yaml`, `deploy/nas/mcp/hb-pa-config.mcp.example.yml`, and the reconciled N5 path-map evidence.

| Parameter | Value |
|---|---|
| NAS service root | `/volume1/personal-assistant` (NAS-local, not SMB/`/Volumes`) |
| App-support root (relocation seam) | `/volume1/personal-assistant/app-support` (via `HB_PA_CONFIG` → `paths.application_support_root`, `config/loader.py` → `config/path_policy.py:57`) |
| DB path (derived) | `/volume1/personal-assistant/app-support/db/hb-personal-assistant.sqlite` |
| Config file on NAS | `/volume1/personal-assistant/config/hb-pa-config.yml` (mounted **read-only**) |
| Obsidian vault (N1B scaffold) | `…/app-support/_vault_disabled` — **deliberately inert** in the backend scaffold config |
| Obsidian vault (N8 live target) | a NAS-local vault path under `/volume1/personal-assistant/…` — **to be set in Phase 04**, never the Mac vault |
| Runtime user | `personal-assistant-svc` = uid `1028`, group `users` = `100` (`compose.yaml` `user: "1028:100"`) |
| Control user | `bfetting` |
| Tailnet exposure | loopback-only default (`HB_PUBLISH_ADDR=127.0.0.1`); tailnet IP redacted as `<nas-tailnet-ip>` in repo |

**Two distinct vault-write systems — do not conflate:**
1. **`nas_mcp`** (N7): the SSH-launched read/write MCP broker (`src/hb_assistant/nas_mcp/*`, config `deploy/nas/mcp/…`), vault mount `/mnt/vault`. Separate process, separate config.
2. **`obsidian_mcp`** (pre-existing, backend): the FastAPI source-indexer + `source_notes` card generator + `mutations.py`. **This is the system N8's bounded ingestion/card proofs target.** Its vault comes from `ObsidianMcpConfig`/`paths.obsidian_vault`.

**Mac vault (must never be the NAS write target):** `/Users/bobbyfetting/Documents/Obsidian Vault/Work/HB Personal Assistant/` (CLAUDE.md). A card write resolving here is a **stop condition**.

## C. Mac-side posture (single-writer preflight — verified this session, read-only)

- **No** `hb-assistant` / `uvicorn` / `analytics.api` / `source-watch` / `scheduler run` / `second-brain` process running. ✅
- **Port 8000 not listening.** ✅
- **launchd finding (single-writer risk):** `com.hb.personal-assistant.scheduler.production` is **registered** (not currently running; last exit 0). Its plist runs:
  ```
  /Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant scheduler run daily-source-refresh --environment production --if-due
  ```
  It targets the **Mac** checkout/venv → **Mac** app-support DB (`~/Library/Application Support/HB Personal Assistant/…`), a *different* DB from the NAS. Because the watcher lease + run lock coordinate **only when both hosts share the same DB/locks dir** (see `02-…-inventory.md`), a NAS scheduler and this Mac agent are **uncoordinated**. Real overlap risk exists if their source roots point at the same synced folders (e.g. SynologyDrive). **Action (deferred, requires Bobby):** unload this agent before NAS scheduler cutover, or keep the NAS as sole scheduler owner. Not modified this session.
- `com.hbintel.*` launchd agents are a **different project** (HB Intel SPFx) — not in scope.

## D. Boundary posture (repo truth + N7 evidence; NAS-side items require on-NAS confirmation with Bobby)

- **No broad passwordless sudo:** N7 established a **narrow** sudoers entry (`deploy/nas/mcp/sudoers.hb-pa-mcp.example`) scoped to the MCP runner only; not a blanket rule. Mac `/etc/sudoers.d` not readable without sudo — not asserted here.
- **No direct SSH for `personal-assistant-svc`:** N7 posture is control-user (`bfetting`) SSH + narrow sudo to invoke the launcher as the service identity; svc has no direct SSH login path provisioned. To be reconfirmed on the NAS in the live-proof session.
- **No public exposure:** repo default is loopback-only; Tailscale Funnel/Serve OFF (N2C/N5C evidence); **no Cloudflare** (N8A explicitly out of scope). NAS firewall/router remains **unconfirmed in-repo** (carried from N2C) — reconfirm on-NAS before any bounded live proof.

## E. Verdict

**PASS (preflight)** to proceed with **non-live** N8 work (inventory, default-off/single-writer hardening, source-identity fix, temp-DB proofs). **HOLD** on all bounded live-NAS proofs (Phases 04–07) pending Bobby's per-step approval and on-NAS reconfirmation of items in §D. One single-writer action item (§C launchd agent) is queued for Bobby.
