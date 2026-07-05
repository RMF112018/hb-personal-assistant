# 14 — Sensitive / Redaction Scan

## Automated gate — `tests/test_repo_sensitive_scan.py`
Result: the repo-wide gate is currently **RED on 16 pre-existing findings, all in files
unrelated to N8B** (synthetic test fixtures / redaction-proof corpora, not real secrets):
- `bearer_token` — `tests/test_procore_full_raw_payload_ingestion.py:179`,
  `tests/test_obsidian_mcp_llm_chat.py:301`, `tests/test_local_model_eval.py:46`,
  `tests/test_phase_10_daily_brief_effectiveness_packets.py:135`,
  `tests/test_phase_10_email_followup_candidate_projection.py:43`,
  `tests/test_obsidian_mcp_oauth.py:730/763/776/816`,
  `subrepos/construction-financial-review/tests/test_safety_scan.py:22`
- `pem_private_key` / `pem_block` — `tests/test_phase_10_daily_brief_effectiveness_packets.py:136`,
  `subrepos/construction-financial-review/tests/test_safety_scan.py:7`
- `client_secret_assignment` — `frontend/src/pages/SettingsPage.test.tsx:345` (`client_secret: ''`, empty-string fixture)
- `oauth_access_token_field` — `frontend/src/components/settings/SourceConnectionsPanel.test.tsx:242` (mock oauth field)

**None of the 16 finding-paths are in this phase's diff** (verified: the git diff touches
only `nas_mcp/*` + `tests/test_nas_mcp_*` + this evidence dir). All 16 predate the branch and
are byte-identical to the foundation tip `cdd29ed0`. The gate is red because these files'
prefixes are not in `_ALLOWED_PREFIXES_BY_RULE` — a pre-existing repo condition, not
introduced by origin auth. Per Bobby's instruction, the allowlist is **not** modified for
unrelated fixtures in this phase; the state is flagged here rather than papered over. (An
earlier draft of this doc mis-stated the count as "2" — that was a `tail`-truncated read of
the assertion output; the accurate count is 16.)

## N8B-added findings: ZERO unallowed
The scanner flags 13 lines in this phase's touched files, **all** of category
`env_secret_assignment` or `msal_cache_content` — both in `_BROADLY_ALLOWED_RULES` (keyword
noise on env-var *name* constants like `HB_MCP_ORIGIN_AUTH_TOKEN_STORE` and the words
`token`/`access_token` in the pre-existing denylist). None are real secrets; none fail the
gate. A raw bearer/token value would trip `bearer_token`/`env_secret_assignment` with a real
payload — none present.

## Manual scan of new/changed files
`src/hb_assistant/nas_mcp/origin_auth.py`, `origin_auth_cli.py`, and
`tests/test_nas_mcp_origin_auth.py`: no NAS hostname, no tailnet-IP literal, no tunnel/API
token, no client secret, no private key, no JWT, no decrypted content. The only token-ish
strings are the env-var **name** `HB_MCP_ORIGIN_AUTH_TOKEN_STORE`, the header literal
`"Bearer "`, and reason-class constants — all non-secret.

## Redaction posture
Committed evidence carries no raw token, no secret, no NAS hostname, no tailnet IP. Tokens
are referenced by **label + fingerprint** only. `mcp.bobby-fetting.me`, `127.0.0.1`, `8765`,
`/volume1`/`/volume2` are non-secret structural constants. Raw runtime artifacts live only
in gitignored `local-sensitive/` at live activation.
