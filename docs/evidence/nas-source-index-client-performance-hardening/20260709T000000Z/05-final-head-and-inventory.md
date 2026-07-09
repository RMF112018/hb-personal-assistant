# 05 — Final HEAD and inventory

## Authoritative closeout tip

| Field | Value |
|-------|-------|
| **Final HEAD** | `21d1aa55eedb524839e59557998ebd88ff954125` |
| **Branch** | `ops/source-index-client-performance-hardening-20260709` |
| **Working tree after this evidence stamp** | will be clean after the commit that includes this file |

### Commit chain (important hashes)

| Role | Hash |
|------|------|
| **Closeout tip (this pack)** | `21d1aa55eedb524839e59557998ebd88ff954125` |
| Evidence reconcile pack | `b695f3c81ad9d65b3c2cc96a5614e560a4b5a66f` |
| Docs hash record | `d8dfa5ee4b2044999f2c1cb181f0abfbdc08f89a` |
| **Implementation** | `6f54bdd017cdb51f6002322b6386f2752324e401` |
| Base `origin/main` (at branch create) | `4c510db65a4fe7409c80e810baf3fd17e316133d` |

### HEAD mismatch resolved

Earlier session summary reported `d8dfa5ee` as HEAD while `04-final-report.md` listed implementation `6f54bdd0` as final commit. Both were true at different times:

1. `6f54bdd0` = feature implementation  
2. `d8dfa5ee` = docs-only update of the report hash field  
3. `b695f3c8` + this tip = full closeout evidence reconciliation  

**Authoritative tip for PR/push decisions:** `21d1aa55eedb524839e59557998ebd88ff954125` (after the stamp commit lands, re-read this file from that commit).

### Recent log (at stamp generation)

```
21d1aa55 (HEAD -> ops/source-index-client-performance-hardening-20260709) docs(evidence): stamp authoritative closeout HEAD hash
b695f3c8 docs(evidence): reconcile HEAD, inventory, and MCP client closeout pack
d8dfa5ee docs(evidence): record final commit hash for source-index hardening
6f54bdd0 feat(nas): source index health, query plan, default-on structure map
4c510db6 Merge pull request #286 from RMF112018/feat/nas-source-structure
e06ce14a feat(nas): source-structure layered index + read-only API + default-off MCP tools (V115)
```

### status -sb (at stamp generation)

```
## ops/source-index-client-performance-hardening-20260709...origin/main [ahead 4, behind 2]
```

### status --short (at stamp generation)

```
(clean)
```

Also: `05-head-reconciliation.md`, `05-git-snapshot.txt`.

## Assistant tool inventory (worktree code + client-style MCP registration)

| Metric | Value | Proof |
|--------|-------|-------|
| Canonical `ALL_ASSISTANT_TOOLS` | **87** | broker constant / inventory tests |
| Groups | **14** | includes `source_structure` |
| Default client-exposed | **87** | `hb_mcp_status.assistant_client_exposed_tool_count` with structure ON |
| Structure kill-switch OFF exposed | **80** | 87 − 7 structure tools |
| Registered `assistant_*` incl. output aliases | **97** | 87 + 10 `assistant_output_*` (writes enabled) |
| Connector tools | **8** | includes health + query_plan |
| Structure tools | **7** | map/route/quality |

Evidence raw dump: `05-mcp-client-discovery.json.txt`.

## Structure default-ON proof

With `HB_MCP_ASSISTANT_SOURCE_STRUCTURE` **unset**:

- `assistant_source_structure_enabled()` → **true**
- `hb_mcp_status.assistant_source_structure_enabled` → **true**
- `assistant_source_structure_tools` length **7**
- Exposure groups include **`source_structure`**
- Tools registered without opt-in: `assistant_source_project_map`, `assistant_source_folder_map`, `assistant_source_index_health`, `assistant_source_query_plan`

## Kill-switch `HB_MCP_ASSISTANT_SOURCE_STRUCTURE=0` proof

- Structure tools **not** registered
- `assistant_source_root_map` dispatch → `ok=false`, error `assistant_source_structure_disabled`
- Connector tools **remain** (health + plan still registered)
- Exposed count **80**

## Discoverability checklist

| Tool / class | Result |
|--------------|--------|
| `assistant_source_index_health` | registered; dispatch ok |
| `assistant_source_query_plan` | registered; dispatch ok |
| `assistant_source_project_map` | registered; gateway query ok |
| `assistant_source_folder_map` | registered |
| `assistant_output_*` (10) | registered; all on `GATEWAY_ALLOWLIST` |

## Live hosted NAS MCP

| Check | Result |
|-------|--------|
| `https://nas-mcp.bobby-fetting.me/health` | **200** ok, `origin_auth_required=true` |
| `https://nas-mcp.bobby-fetting.me/mcp` | **401** unauthorized (no origin bearer in session) |

See `05-live-nas-mcp-probe.md`. Authenticated live matrix still pending operator credentials.

## Pytest

| Artifact | Content |
|----------|---------|
| `05-final-pytest-command.txt` | Exact command only |
| `05-final-pytest-with-command.txt` | Command + full run, **exit 0** |
| `final-pytest.txt` | Earlier output-only run |

## Push / PR gate

**Do not push or open a PR** until live connected-client matrix is completed with origin auth, **or** the operator explicitly accepts PR with live validation pending.

Operator script: `03-operator-connected-client-test-script.md`  
Offline matrix: `05-offline-prompt-matrix.json.txt`
