# 00 — N8B Safe-Mode / Limits / Freshness Closeout

**Phase:** N8B-Safe-Mode-Limits-Freshness — pre-Cloudflare local-origin hardening
**Stamp:** `20260705T101153Z` · **Branch:** `ops/nas-mcp-safe-mode-limits-freshness-n8b-20260705T101153Z`
**Base:** origin-auth tip `0633514d` (off `origin/main` @ `7f22fa9d`; foundation + origin-auth present)
**Verdict: HOLD — safe-mode/limits/freshness/override layer PASS; full N8B remains gated on live Cloudflare Access proof, MCP/cloudflared reboot and failure-restart proof, Claude/ChatGPT/Grok client-compat proof, forbidden-surface negative tests, and rollback proof.**

## Delivered
1. **Safe mode** (`profile.safe_mode_enabled` + broker) — `HB_MCP_SAFE_MODE=1` denies every mutation (`safe_mode_active:<tool>`) while keeping reads/status/freshness; visible in `hb_mcp_status`/`hb_capability_mode`; operator/env-only (no MCP toggle); origin auth still required. (`02`–`04`)
2. **Rate limits / abuse containment** (`limits.py`) — env-overridable (`HB_MCP_MAX_*`) + operator-override-aware, raise-only, fail-closed: response bytes, DB rows, search results, file excerpt, card size (reused existing bounds); net-new **per-window AI-Outputs write limiter** (mutations.jsonl) and **concurrency cap**. The write limiter **fails closed on unreadable/corrupt receipt state** (`write_rate_state_unavailable`) — only a missing file on a clean first run counts as 0. Binary/broad-scan denial reused. (`05`–`07`)
3. **Operator-scoped overrides** (`overrides.py` + `override_cli.py`) — local/CLI-only (no MCP tool mints one → no remote self-approval), narrow (scope/client/tool), **required reason + expiry**, revocable, raise-only, audited; status readable via `hb_capability_mode`. (`08`–`10`)
4. **Read-only freshness/queue/failures/status** (`freshness.py`) — aggregate-only curated SQL over a hardcoded table set (mode=ro + `query_only`), table-existence-guarded → explicit `not_configured`/`unknown`/`ok`/`stale`; new Tier-0 tools `hb_data_freshness`/`hb_queue_status`/`hb_recent_failures`/`hb_last_successful_runs`/`hb_capability_mode`; no raw rows/paths/content; watcher reported `unknown` (in-memory only). Also fixed the broken `schema_version`→`schema_migrations` allowlist entry. (`11`–`14`)
5. **Capability + origin-auth integration** — new tools Tier 0, require origin auth; overrides never remotely creatable; valid tokens never bypass tiers; per-token `allowed_tools` only narrows. (`15`, `16`)
6. **Audit** extended with `safe_mode`, `capability_tier`, `rate_limit_result`, `override_id`. (`17`)

## Tests / gates
`tests/test_nas_mcp_safe_mode_limits_freshness.py` (23) → **full NAS suite 81 passed**, ruff clean, `git diff --check` clean. Sensitive scan: **zero phase-added findings** (repo gate red only on the 16 pre-existing unrelated fixtures, `18`). No deploy files changed.

## HOLD (acceptable per phase criteria)
- **Timeout** is best-effort: `HB_MCP_TOOL_TIMEOUT_SECONDS` config + post-hoc `slow_tool` audit flag; hard pre-emption of arbitrary sync tools is documented HOLD (static per-call bounds + concurrency cap + response cap bound real work). (`05`)
- Subsystem freshness fields absent in this DB are reported `not_configured`/`unknown`, not fabricated.
- Live Cloudflare / client-compat / reboot / rollback proofs remain later sub-phases.

## Commit posture
Uncommitted, unpushed. Commit locally only after Bobby reviews the diff and authorizes. No push.
