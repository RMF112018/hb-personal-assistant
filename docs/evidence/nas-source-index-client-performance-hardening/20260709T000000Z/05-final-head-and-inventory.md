# 05 — Final HEAD and inventory

Generated during closeout reconciliation. **Note:** if this file is committed after generation, HEAD advances by one commit; the commit that contains this file is the authoritative closeout tip unless a later commit is made.

## Git

| Field | Value |
|-------|-------|
| Branch | `ops/source-index-client-performance-hardening-20260709` |
| HEAD at generation | `d8dfa5ee4b2044999f2c1cb181f0abfbdc08f89a` |
| Working tree | `dirty` (uncommitted closeout evidence may be present when this file was first written) |
| Base / origin main | `4c510db65a4fe7409c80e810baf3fd17e316133d` |
| Implementation commit | `6f54bdd017cdb51f6002322b6386f2752324e401` |
| Docs-hash evidence commit | `d8dfa5ee4b2044999f2c1cb181f0abfbdc08f89a` |

### Recent log

```
d8dfa5ee (HEAD -> ops/source-index-client-performance-hardening-20260709) docs(evidence): record final commit hash for source-index hardening
6f54bdd0 feat(nas): source index health, query plan, default-on structure map
4c510db6 Merge pull request #286 from RMF112018/feat/nas-source-structure
e06ce14a feat(nas): source-structure layered index + read-only API + default-off MCP tools (V115)
13a4e1a2 Merge pull request #285 from RMF112018/fix/nas-mcp-freshness-defect6
```

### status -sb

```
## ops/source-index-client-performance-hardening-20260709...origin/main [ahead 2, behind 2]
?? docs/evidence/nas-source-index-client-performance-hardening/20260709T000000Z/05-final-pytest-command.txt
?? docs/evidence/nas-source-index-client-performance-hardening/20260709T000000Z/05-final-pytest-with-command.txt
?? docs/evidence/nas-source-index-client-performance-hardening/20260709T000000Z/05-git-snapshot.txt
?? docs/evidence/nas-source-index-client-performance-hardening/20260709T000000Z/05-head-reconciliation.md
?? docs/evidence/nas-source-index-client-performance-hardening/20260709T000000Z/05-mcp-client-discovery.json.txt
?? docs/evidence/nas-source-index-client-performance-hardening/20260709T000000Z/05-offline-prompt-matrix.json.txt
```

### status --short (at generation)

```
?? docs/evidence/nas-source-index-client-performance-hardening/20260709T000000Z/05-final-pytest-command.txt
?? docs/evidence/nas-source-index-client-performance-hardening/20260709T000000Z/05-final-pytest-with-command.txt
?? docs/evidence/nas-source-index-client-performance-hardening/20260709T000000Z/05-git-snapshot.txt
?? docs/evidence/nas-source-index-client-performance-hardening/20260709T000000Z/05-head-reconciliation.md
?? docs/evidence/nas-source-index-client-performance-hardening/20260709T000000Z/05-mcp-client-discovery.json.txt
?? docs/evidence/nas-source-index-client-performance-hardening/20260709T000000Z/05-offline-prompt-matrix.json.txt
```

See also: `05-head-reconciliation.md`, `05-git-snapshot.txt`.

## Assistant tool inventory (repo truth, worktree code)

| Metric | Value | Proof |
|--------|-------|-------|
| Canonical `ALL_ASSISTANT_TOOLS` | **87** | `len(ALL_ASSISTANT_TOOLS)` / 14 groups |
| Groups | **14** | includes `source_structure` |
| Default client-exposed (structure ON) | **87** | `hb_mcp_status.assistant_client_exposed_tool_count` |
| Structure kill-switch OFF exposed | **80** | 87 − 7 structure tools |
| `assistant_*` registered including output aliases | **97** | 87 + 10 `assistant_output_*` when write gate on |
| Connector tools | **8** | + `assistant_source_index_health`, `assistant_source_query_plan` |
| Structure tools | **7** | map/route/quality |

## Structure default-ON proof

From client-style MCP registration (`05-mcp-client-discovery.json.txt`):

- `structure_enabled_env_unset`: **true** when `HB_MCP_ASSISTANT_SOURCE_STRUCTURE` is unset
- `status_structure_enabled`: **true**
- `status_structure_tools_count`: **7**
- Exposure groups include `source_structure`
- Tools discoverable without enabling env:  
  `assistant_source_project_map`, `assistant_source_folder_map`, `assistant_source_index_health`, `assistant_source_query_plan`

## Kill-switch `HB_MCP_ASSISTANT_SOURCE_STRUCTURE=0` proof

- `status_structure_enabled`: **false**
- `status_structure_tools`: `[]`
- Structure tools **not** registered
- Dispatch `assistant_source_root_map` → `ok=false`, error `assistant_source_structure_disabled`
- Connector health/plan **remain** registered: `assistant_source_index_health`, `assistant_source_query_plan`
- Exposed count: **80** (structure-only hide)

## Discoverability of required tools / aliases

| Tool / class | Discoverable (default ON) |
|--------------|---------------------------|
| `assistant_source_index_health` | yes (registered + dispatch ok) |
| `assistant_source_query_plan` | yes (dispatch ok; intent `map_project_folder` for map prompt) |
| `assistant_source_project_map` | yes + gateway `hb_assistant_tool_query` ok |
| `assistant_source_folder_map` | yes |
| `assistant_output_*` (10 aliases) | yes registered; all on `GATEWAY_ALLOWLIST` |

## Live hosted NAS MCP

| Check | Result |
|-------|--------|
| `https://nas-mcp.bobby-fetting.me/health` | HTTP 200 — `surface=nas_mcp`, `origin_auth_required=true` |
| `https://nas-mcp.bobby-fetting.me/mcp` | HTTP 401 unauthorized (no origin bearer in this session) |

Hosted authenticated tool listing was **not** completed here. Client-equivalent proof uses the same FastMCP `register_nas_mcp_tools` + broker path as `scripts/smoke-n8c-client-exposure.sh`.

## Pytest closeout

- Exact command: `05-final-pytest-command.txt`
- Command + full output: `05-final-pytest-with-command.txt` (exit 0)
- Prior output-only artifact: `final-pytest.txt`

## Push / PR gate

**Do not push or open a PR** until:

1. Live connected-client matrix is run with origin auth against `nas-mcp.bobby-fetting.me`, **or**
2. Operator explicitly accepts opening PR with live validation pending.

Operator matrix: `03-operator-connected-client-test-script.md`. Offline routing matrix: `05-offline-prompt-matrix.json.txt`.
