# 04 — Home / Work read-only tools

## Root mapping

| root_key | Host path | Container mount | Mode |
|---|---|---|---|
| `home` | `/volume1/homes/bfetting/Home` | `/mnt/roots/home` | read_only |
| `work` | `/volume1/homes/bfetting/Work` | `/mnt/roots/work` | read_only |

Legacy `syn-work` mount removed from compose.

## Tools

Implemented in `src/hb_assistant/nas_mcp/root_tools.py`:

| Tool | Purpose |
|---|---|
| `hb_root_list` | Directory listing |
| `hb_root_stat` | File/dir metadata |
| `hb_root_search` | Filename search within subtree |
| `hb_root_read_excerpt` | Bounded text excerpt (plain text paths) |
| `hb_root_read_file` | Typed read via `file_readers.py` |

`root_key` enum enforced: **`home`** | **`work`** only.

## Write denial

- No write/delete/move tools registered for `home` or `work`
- `root_policy.assert_write()` rejects read-only roots
- Output sandbox tools fixed to `outputs` root only — cannot write to home/work

## Security (shared with vault)

- Relative paths only; absolute paths rejected
- `../` traversal rejected
- Symlink escape guard (`path_safe.resolve_under_root` + `realpath`)
- Denied name patterns: `.enc`, token/cache/key patterns
- Denied dir segments: `.obsidian`, `auth`, `security`, `secrets`, etc.
- Responses use `path_display: home/...` or `work/...`; no `/volume1/` leak

## Local test evidence

| Test | Result |
|---|---|
| `test_home_read_and_write_denied` | PASS — list home OK; traversal write to `../home/` denied |
| `test_work_read_only` | PASS — stat + read_file on CSV; no `/volume1/` in JSON |

## NAS functional proof

**Deferred.** NAS confirmed Home and Work host dirs exist; MCP probes not run.

Home/Work **write denial on NAS not proven** — local tests only.
