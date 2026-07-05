# 28 — AI Outputs Write Proof

`tests/test_nas_mcp_remote_profile.py` — run with `PYTHONPATH=src pytest`, temp-vault fixtures, no live NAS. **6 passed** (full profile suite).

## `test_ai_outputs_create_update_append` — PASS
Under `HB_MCP_PROFILE=remote_cloudflare`:
1. **create** — `ai_outputs_card_upsert(title="Test Card", body="hello", tags=["a"], source_client="claude", mode="create")` → `ok`; `relative_path == "AI Outputs/Test Card.md"`; the file exists at `<vault>/AI Outputs/Test Card.md`; returns `sha256`.
2. **update requires SHA** — `mode="update"` with **no** `expected_sha` → refused; with a **wrong** `expected_sha` (`deadbeef`) → refused; with the **correct** sha → `ok`.
3. **append** — `mode="append"` (source_client `grok`) → `ok`; the card now contains the appended text.
4. A **mutation receipt** (`mutations.jsonl`) is written under the obsidian support dir.

## What this proves
- The single sanctioned remote write lands **only** under `AI Outputs/`.
- Optimistic-concurrency (SHA) blocks blind overwrites.
- Every write is receipted with client attribution.

## Broader suite
`test_nas_mcp_remote_profile.py` (6), `test_nas_mcp_files_rw.py`, `test_nas_mcp_readonly.py`, `test_nas_mcp_obsidian_adapter_redaction.py` → **39 passed** together. ruff clean on all changed files.
