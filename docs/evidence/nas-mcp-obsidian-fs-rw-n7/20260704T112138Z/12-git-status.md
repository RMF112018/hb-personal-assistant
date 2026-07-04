# 12 — Git status

**Snapshot:** final pre-commit (N7-FS-RW closeout)

| Item | Value |
|---|---|
| Branch | `feat/nas-mcp-ssh-launcher-n7-20260704T102041Z` |
| Ahead of `origin/main` (pre-commit) | 20 |
| Behind `origin/main` | 0 |
| N7-FS-RW | committing in this step |
| Push / PR | Not authorized |

## Intended commit scope

### Modified

```
 M deploy/nas/mcp/check-mcp-compose.sh
 M deploy/nas/mcp/compose-mcp.yaml
 M deploy/nas/mcp/hb-pa-config.mcp.example.yml
 M src/hb_assistant/nas_mcp/broker.py
 M src/hb_assistant/nas_mcp/config.py
 M src/hb_assistant/nas_mcp/server.py
 M src/hb_assistant/obsidian_mcp/mutations.py
 M tests/test_nas_mcp_readonly.py
```

### Added

```
?? docs/evidence/nas-mcp-obsidian-fs-rw-n7/20260704T112138Z/*.md
?? src/hb_assistant/nas_mcp/file_readers.py
?? src/hb_assistant/nas_mcp/file_writers.py
?? src/hb_assistant/nas_mcp/obsidian_adapter.py
?? src/hb_assistant/nas_mcp/obsidian_config.py
?? src/hb_assistant/nas_mcp/output_tools.py
?? src/hb_assistant/nas_mcp/root_policy.py
?? src/hb_assistant/nas_mcp/root_tools.py
?? src/hb_assistant/nas_mcp/tool_registration.py
?? tests/test_nas_mcp_files_rw.py
```

## Excluded from commit

- `docs/evidence/nas-mcp-obsidian-fs-rw-n7/20260704T112138Z/local-sensitive/` (operator gate; not committed)
- DB files, vault/source-root contents, NAS probe artifacts, tarballs, secrets, sudoers live files

## Scope check

All staged paths are within **code / tests / deploy / evidence** scope. No unrelated files dirty.

Suggested commit message:

`feat(nas): expand MCP filesystem roots and Obsidian write parity`
