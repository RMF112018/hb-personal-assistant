# 16 — Git Status

**Nothing pushed. No commit yet (awaiting Bobby's review + authorization).**

- **Branch:** `ops/nas-mcp-origin-auth-n8b-20260705T092719Z`
- **Base:** foundation tip `cdd29ed0` (3 foundation commits ahead of `origin/main` @ `7f22fa9d`)
- **Worktree:** `/Users/bobbyfetting/hb-pa-n8b-20260705T090033Z`

## Changed files (code/tests — +79/−7 tracked, plus 3 new files)
- **New:** `src/hb_assistant/nas_mcp/origin_auth.py`, `src/hb_assistant/nas_mcp/origin_auth_cli.py`, `tests/test_nas_mcp_origin_auth.py`.
- **Modified:** `src/hb_assistant/nas_mcp/broker.py` (auth context → audit + per-token narrowing), `config.py` (`origin_auth_store_path`), `profile.py` (`origin_auth_required` / `health_mode` / `gate_status`), `server.py` (middleware wrap + minimal-public health), `tests/test_nas_mcp_readonly.py` (health contract).
- **Evidence:** `docs/evidence/nas-mcp-origin-auth-n8b/20260705T092719Z/` (17 `NN-*.md` + `local-sensitive/README.md`).

No secret/token committed. `origin-auth/tokens.json` is a runtime artifact under app-support
(outside the repo) — never created or committed by this phase.

## Recommended commit split (after authorization)
1. `nas-mcp: add origin auth middleware and token store integration` — `origin_auth.py`, `profile.py`, `config.py`, `server.py`, `broker.py`.
2. `nas-mcp: add origin auth tests and audit attribution` — `tests/test_nas_mcp_origin_auth.py`, `tests/test_nas_mcp_readonly.py`, `origin_auth_cli.py`.
3. `docs: add N8B origin auth evidence` — the evidence directory.

## Push posture
Unpushed. **No push** until Bobby authorizes.
