# 05 — Final HEAD and inventory

## Authoritative tip

| Field | Value |
|-------|-------|
| **Final HEAD** | `38741bcc7ffd501c9c7f8d6e35084d55b6304d43` |
| **Branch** | `ops/source-index-client-performance-hardening-20260709` |
| **Working tree at generation of this content** | see status below; commit this file for clean tree |

### Verify

```bash
cd <worktree>
git rev-parse HEAD
git log --oneline --decorate -8
git status --short
```

### Commit roles

| Role | Hash |
|------|------|
| **Tip when this file content was generated** | `38741bcc7ffd501c9c7f8d6e35084d55b6304d43` |
| Closeout evidence pack | `b695f3c81ad9d65b3c2cc96a5614e560a4b5a66f` |
| Docs hash record | `d8dfa5ee4b2044999f2c1cb181f0abfbdc08f89a` |
| **Implementation** | `6f54bdd017cdb51f6002322b6386f2752324e401` |
| Base at branch create | `4c510db65a4fe7409c80e810baf3fd17e316133d` |

### HEAD mismatch resolved

| Claim | Hash | Meaning |
|-------|------|---------|
| Session summary HEAD | `d8dfa5ee` | Tip after docs-only hash note |
| Old final-report final commit | `6f54bdd0` | Implementation only |
| **Use for tip** | `38741bcc7ffd501c9c7f8d6e35084d55b6304d43` (then re-run `git rev-parse HEAD` after any later commit) | Branch tip |

### Recent log (at generation)

```
38741bcc (HEAD -> ops/source-index-client-performance-hardening-20260709) docs(evidence): final HEAD stamp for closeout tip
bdced1be docs(evidence): fix closeout HEAD inventory text and final report
21d1aa55 docs(evidence): stamp authoritative closeout HEAD hash
b695f3c8 docs(evidence): reconcile HEAD, inventory, and MCP client closeout pack
d8dfa5ee docs(evidence): record final commit hash for source-index hardening
6f54bdd0 feat(nas): source index health, query plan, default-on structure map
4c510db6 Merge pull request #286 from RMF112018/feat/nas-source-structure
e06ce14a feat(nas): source-structure layered index + read-only API + default-off MCP tools (V115)
```

### status -sb

```
## ops/source-index-client-performance-hardening-20260709...origin/main [ahead 6, behind 2]
```

### status --short

```
(clean)
```

## Assistant tool inventory

| Metric | Value |
|--------|-------|
| Canonical ALL_ASSISTANT_TOOLS | **87** |
| Groups | **14** |
| Default client-exposed | **87** (structure default-ON) |
| Structure kill-switch OFF | **80** |
| assistant_* with output aliases | **97** (87+10) |
| Connector tools | **8** |
| Structure tools | **7** |

Raw proof: `05-mcp-client-discovery.json.txt`.

## Structure default-ON

- Env unset → enabled true
- Status exposes 7 structure tools; group `source_structure` present
- Discoverable: `assistant_source_index_health`, `assistant_source_query_plan`, `assistant_source_project_map`, `assistant_source_folder_map`

## Kill-switch HB_MCP_ASSISTANT_SOURCE_STRUCTURE=0

- Structure tools unregistered; dispatch root_map → `assistant_source_structure_disabled`
- Health/plan remain; exposed 80

## assistant_output_* aliases

All 10 registered and on GATEWAY_ALLOWLIST.

## Live NAS MCP

| URL | Result |
|-----|--------|
| https://nas-mcp.bobby-fetting.me/health | **200** |
| https://nas-mcp.bobby-fetting.me/mcp | **401** (origin auth required; no bearer in session) |

See `05-live-nas-mcp-probe.md`.

## Pytest

| File | Purpose |
|------|---------|
| `05-final-pytest-command.txt` | Exact command |
| `05-final-pytest-with-command.txt` | Command + output, exit 0 |

## Push/PR gate

Do not push/PR until live connected-client matrix with origin auth, or operator accepts pending live validation.

Operator: `03-operator-connected-client-test-script.md`  
Offline matrix: `05-offline-prompt-matrix.json.txt`

## Post-commit tip file

See `05-TIP.txt` for the hash of the commit that last froze this inventory body (parent of any pure tip stamp). After this tip file commit, **`git rev-parse HEAD` is authoritative.**
