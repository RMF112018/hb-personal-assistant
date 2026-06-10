# CLI Smoke Results — Prompt 05

All commands run via `python -m hb_assistant.cli.main` (the venv console-script shim is the
empty 3.14 interpreter). Disposable temp DB + safe committed fixture only.

## 1. files parse-index --no-json  (exit + header)
```
# File Parse Index (review-safe read-model)

_files: 1 · by status: {'parsed': 1} · by extension: {'.txt': 1} · local-only, hash-only, no model._

## Files
- **note.txt** (.txt · text/plain) → **parsed** via stdlib-text
  - id: file:59700155e034d16d · text_length: 60 · excerpt-hash: sha256:36481ad3cafc2ef2f47a536a7e2b391568b219343af9196c2e5a620c35d9060c · counts: —
EXIT=0
```
## 2. files parse-index --json  (relevant keys)
```
      "parsed_status": "parsed",
      "text_length": 60,
      "text_excerpt_hash": "sha256:36481ad3cafc2ef2f47a536a7e2b391568b219343af9196c2e5a620c35d9060c",
      "hash_scope": "text_excerpt",
```
## 3. daily-brief mcp-packet --no-json  (header + safety)
```
# MCP Context Packet

_Contract phase10-mcp-1.0 · purpose `daily_brief_local_agent_context` · generated 2026-06-09T05:00:00-04:00 · brief 2026-06-09_

EXIT=0
```
## 4. daily-brief mcp-packet --json  (contract + guardrail)
```
  "packet_contract_version": "phase10-mcp-1.0",
  "ok": true,
    "no_raw_content": true,
    "no_external_writeback": true,
```
