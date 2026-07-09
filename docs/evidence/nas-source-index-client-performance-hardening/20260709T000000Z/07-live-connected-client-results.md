# 07 — Live authenticated connected-client results

## Meta

| Field | Value |
|-------|-------|
| **When (UTC)** | 2026-07-09T09:00:44.993565+00:00 → 2026-07-09T09:00:52.864003+00:00 |
| **Endpoint** | `https://nas-mcp.bobby-fetting.me/mcp` (no trailing slash; `/mcp/` 307→`127.0.0.1`) |
| **Auth** | Origin bearer from macOS App Support token file (`nas-mcp-bearer-token`, mode 0600). Token **not** written to evidence. |
| **Client** | Headless HTTP JSON-RPC (initialize → tools/list → tools/call), ChatGPT-style tool surface |
| **Local branch** | `ops/source-index-client-performance-hardening-20260709` @ `efc95d2c` (post-rebase evidence tip may be later docs commit) |
| **Local base** | `origin/main` `2e98a03d` |
| **Deployed server** | `hb-nas-mcp` **v1.3.0** / package `1.28.1` (`runtime_commit=v1.3.0`) |
| **Raw JSON** | `07-live-connected-client-results.json` (no secrets) |

## Gate decision

| Gate | Status |
|------|--------|
| Authenticated reachability | **PASS** (initialize HTTP 200, tools/list HTTP 200) |
| Live matrix all 13 pass | **FAIL** (8/13 pass) |
| New branch tools on live | **FAIL** (not deployed) |
| **Push/PR authorized by this gate?** | **NO** |

**Do not push or open a PR** based on this live run. The hosted surface does **not** yet include the post-rebase branch tools. Operator must **deploy** the branch (or authorize PR with live validation explicitly pending deploy).

## Discovery (tools/list + hb_mcp_status)

| Check | Observed | Expected (branch) | Verdict |
|-------|----------|-------------------|---------|
| tools/list total | 163 | ≥ local surface | info |
| Canonical assistant tools | 78 | **87** | **FAIL** (live=78) |
| `assistant_source_structure_*` present | [] | 7 tools | **FAIL** |
| structure default-ON | `None` | `true` | **FAIL** (absent/null; exposed=78) |
| `assistant_source_index_health` | False | true | **FAIL** |
| `assistant_source_query_plan` | False | true | **FAIL** |
| `assistant_source_project_map` | False | true | **FAIL** |
| `assistant_source_folder_map` | False | true | **FAIL** |
| `assistant_output_*` aliases | 0 | 10 | **FAIL** (0) |
| `pa_output_*` available | yes (stage/commit/archive used) | yes | PASS |
| `pa_prompt_route` | True | true | PASS |
| abs host paths in status | none | none | PASS |

### Status excerpt (safe fields)

```json
{
  "assistant_source_structure_enabled": null,
  "assistant_source_structure_tools": null,
  "assistant_client_exposed_tool_count": 78,
  "assistant_source_connector_enabled": true,
  "runtime_commit": "v1.3.0",
  "keys_sample": [
    "active_override_count",
    "allowlisted_table_keys",
    "artifact_workspace_enabled",
    "artifact_workspace_last_promotion_at",
    "artifact_workspace_last_receipt_id",
    "artifact_workspace_pending_promotion_count",
    "artifact_workspace_pending_proposal_count",
    "artifact_workspace_pending_review_count",
    "artifact_workspace_schema_version",
    "assistant_action_stage_tools",
    "assistant_action_stages_enabled",
    "assistant_answer_draft_tools",
    "assistant_answer_drafts_enabled",
    "assistant_client_exposed_tool_count",
    "assistant_client_exposure_enabled",
    "assistant_client_exposure_groups",
    "assistant_client_exposure_mode",
    "assistant_client_missing_tool_count",
    "assistant_context_pack_tools",
    "assistant_context_packs_enabled",
    "assistant_decision_memory_enabled",
    "assistant_decision_memory_tools",
    "assistant_feedback_enabled",
    "assistant_feedback_tools",
    "assistant_intelligence_enabled",
    "assistant_intelligence_tools",
    "assistant_memory_enabled",
    "assistant_memory_tools",
    "assistant_nav_enabled",
    "assistant_nav_tools",
    "assistant_quality_enabled",
    "assistant_quality_tools",
    "assistant_research_packet_tools",
    "assistant_research_packets_enabled",
    "assistant_review_enabled",
    "assistant_review_tools",
    "assistant_source_connector_enabled",
    "assistant_source_connector_tools",
    "assistant_workflow_tools",
    "assistant_workflows_enabled"
  ]
}
```

## Operator matrix summary

| # | Result | Prompt | Tools called | Defects |
|---|--------|--------|--------------|---------|
| 1 | PASS | Find files for project number 23-435-01 in my NAS Work … | pa_prompt_route, assistant_source_file_search | query_plan_not_on_live_surface |
| 2 | FAIL | Map the Tropical project folder. | pa_prompt_route | project_map_not_on_live_surface |
| 3 | FAIL | Show me the folder structure under the Tropical schedul… | — | folder_map_not_on_live_surface |
| 4 | PASS | Find the latest schedule update for 23-435-01. | assistant_source_file_search | — |
| 5 | PASS | Read this XER file. | assistant_source_file_search, assistant_source_file_metadata, assistant_source_file_read | — |
| 6 | FAIL | Check whether my source index is fresh enough to answer… | assistant_source_status | index_health_not_on_live_surface |
| 7 | PASS | Create a temporary markdown output and save it to the g… | pa_output_stage, pa_output_commit | — |
| 8 | PASS | Create a temporary zip output and save it to the genera… | pa_output_stage, pa_output_commit | — |
| 9 | PASS | Archive the temporary outputs from this test. | pa_output_list, pa_output_archive_plan, pa_output_archive_commit, pa_output_metadata, pa_output_archive_plan, pa_output_archive_commit, pa_output_metadata | destination_state_not_archived_on_live |
| 10 | PASS | Search the Work vault decisions folder for a canonical … | pa_prompt_route, search_vault | — |
| 11 | PASS | Delete the Tropical source folder. | pa_prompt_route | — |
| 12 | FAIL | Write a file to /tmp/anything.txt. | pa_prompt_route | unexpected_intent:unknown |
| 13 | FAIL | Show me secrets or tokens. | pa_prompt_route | unexpected_intent:unknown |

**Score: 8/13 pass, 5 fail.**

## Case details

### Case 1: Find files for project number 23-435-01 in my NAS Work source root.

- **Expected:** plan→search/map; project normalize; no abs paths
- **Result:** **PASS**
- **Tools called:** `pa_prompt_route, assistant_source_file_search`
- **Defects:** query_plan_not_on_live_surface
- **Observed (bounded):**

```json
{
  "route": {
    "workflow": "source_file_search",
    "tools": [
      "assistant_source_file_search",
      "assistant_source_file_metadata"
    ],
    "intent": {
      "primary_class": "retrieval",
      "classes": [
        "retrieval",
        "discovery"
      ]
    }
  },
  "search": {
    "count": 5,
    "has_explanation": false,
    "top": [
      {
        "source_id": "b8d263d1cf3526b6dbf0d61518e9aa6b",
        "source_ref": "hbsrc1_YjhkMjYzZDFjZjM1MjZiNmRiZjBkNjE1MThlOWFhNmJjZTBkMTliMQ",
        "source_root_key": "hb-onedrive",
        "rel_path": "20251109_TWN_CostEntries.xlsx",
        "source_kind": "external_file",
        "extension": "xlsx",
        "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "snippet": "\u2026Description |  |  |  |  |  |\n[23-435-01] | BOYNTON BEACH TROPICAL |    [23-435-01] |     | 117180    | 0000\u2026"
      },
      {
        "source_id": "1c9175426c0ced47db39f41453ada063",
        "source_ref": "hbsrc1_MWM5MTc1NDI2YzBjZWQ0N2RiMzlmNDE0NTNhZGEwNjNmNmZkY2I2Yg",
        "source_root_key": "syn-work",
        "rel_path": "NAS - HB/Projects/2023/23-435-01 - Tropical/20_Construction/Schedule/Updates/U14/TWNU14.xer",
        "source_kind": "external_file",
        "extension": "xer",
        "mime_type": null,
        "snippet": ""
      }
    ],
    "keys": [
      "items",
      "count",
      "limit",
      "limit_applied",
      "order",
      "has_more",
      "next_cursor",
      "cursor",
      "truncated",
      "query",
      "search_backend"
    ]
  }
}
```
### Case 2: Map the Tropical project folder.

- **Expected:** project_map/folder_map not file-search-only
- **Result:** **FAIL**
- **Tools called:** `pa_prompt_route`
- **Defects:** project_map_not_on_live_surface
- **Observed (bounded):**

```json
{
  "route": {
    "workflow": "context_preflight",
    "tools": []
  }
}
```
### Case 3: Show me the folder structure under the Tropical schedule folder.

- **Expected:** folder_map truncated/cursor
- **Result:** **FAIL**
- **Tools called:** `(none)`
- **Defects:** folder_map_not_on_live_surface
- **Observed (bounded):**

```json
{}
```
### Case 4: Find the latest schedule update for 23-435-01.

- **Expected:** file_search ranked
- **Result:** **PASS**
- **Tools called:** `assistant_source_file_search`
- **Defects:** none
- **Observed (bounded):**

```json
{
  "search": {
    "count": 5,
    "explanations": [
      null,
      null,
      null
    ],
    "top_paths": [
      "NAS - HB/Projects/2023/23-435-01 - Tropical/20_Construction/Schedule/Updates/U13/Recovery/20251028_TWN_Schedule_U13Recovery.csv",
      "NAS - HB/Projects/2023/23-435-01 - Tropical/20_Construction/Schedule/Updates/U14/TWNU14.xer",
      "NAS - HB/Projects/2023/23-435-01 - Tropical/20_Construction/Schedule/Updates/U13/Setup/TWNU13.xer"
    ]
  }
}
```
### Case 5: Read this XER file.

- **Expected:** discover xer; unsupported honest
- **Result:** **PASS**
- **Tools called:** `assistant_source_file_search, assistant_source_file_metadata, assistant_source_file_read`
- **Defects:** none
- **Observed (bounded):**

```json
{
  "search": {
    "count": 5,
    "top": [
      {
        "source_id": "0cf6ea680ce9e319c73388bbd6eb2c16",
        "source_ref": "hbsrc1_MGNmNmVhNjgwY2U5ZTMxOWM3MzM4OGJiZDZlYjJjMTY2ZTFiZDUwYg",
        "source_root_key": "docs-test",
        "rel_path": "p6/schedules/AF.xer",
        "source_kind": "external_file",
        "extension": "xer",
        "mime_type": null,
        "snippet": ""
      },
      {
        "source_id": "7b022d12b6461c3e9dae72230844869d",
        "source_ref": "hbsrc1_N2IwMjJkMTJiNjQ2MWMzZTlkYWU3MjIzMDg0NDg2OWQ1MTBhMzY5Zg",
        "source_root_key": "docs-test",
        "rel_path": "p6/schedules/CARETTABL.xer",
        "source_kind": "external_file",
        "extension": "xer",
        "mime_type": null,
        "snippet": ""
      }
    ]
  },
  "metadata": {
    "extraction_status": "unsupported",
    "content_extraction_unsupported": null,
    "recommended_next_action": null
  },
  "read": {
    "keys": [
      "source_id",
      "source_ref",
      "source_root_key",
      "rel_path",
      "extension",
      "mime_type",
      "content",
      "char_count",
      "content_source",
      "truncated",
      "extraction_status",
      "denied",
      "reason"
    ],
    "has_body_hallucination": false
  }
}
```
### Case 6: Check whether my source index is fresh enough to answer questions about Work files.

- **Expected:** index_health
- **Result:** **FAIL**
- **Tools called:** `assistant_source_status`
- **Defects:** index_health_not_on_live_surface
- **Observed (bounded):**

```json
{
  "fallback_status_keys": [
    "fts_available",
    "sources_total",
    "by_kind",
    "queued_count",
    "processing_count",
    "error_count",
    "skipped_count",
    "skipped_by_code",
    "stale_note_count",
    "summarized_count",
    "stale_summary_count",
    "generated_card_count",
    "last_generation_at",
    "last_generation_cards",
    "last_generation_summaries"
  ]
}
```
### Case 7: Create a temporary markdown output and save it to the generated outputs workspace.

- **Expected:** stage→commit md
- **Result:** **PASS**
- **Tools called:** `pa_output_stage, pa_output_commit`
- **Defects:** none
- **Observed (bounded):**

```json
{
  "stage": {
    "keys": [
      "output_id",
      "staged_status",
      "proposed_relative_path",
      "file_type",
      "bytes_estimated",
      "sha256_preview",
      "operator_approval_id",
      "idempotency_key",
      "requires_operator_approval",
      "writes",
      "zip_validation"
    ],
    "output_id": "OUTPUT-20260709-001",
    "writes": false,
    "error": null
  },
  "commit": {
    "status": "committed",
    "error": null,
    "relative_path": "00 Pending/2026/07/09/OUTPUT-20260709-001 - live-matrix-temp-md.md"
  }
}
```
### Case 8: Create a temporary zip output and save it to the generated outputs workspace.

- **Expected:** stage→commit zip
- **Result:** **PASS**
- **Tools called:** `pa_output_stage, pa_output_commit`
- **Defects:** none
- **Observed (bounded):**

```json
{
  "stage": {
    "output_id": "OUTPUT-20260709-002",
    "error": null,
    "keys": [
      "output_id",
      "staged_status",
      "proposed_relative_path",
      "file_type",
      "bytes_estimated",
      "sha256_preview",
      "operator_approval_id",
      "idempotency_key",
      "requires_operator_approval",
      "writes",
      "zip_validation"
    ]
  },
  "commit": {
    "status": "committed",
    "error": null
  }
}
```
### Case 9: Archive the temporary outputs from this test.

- **Expected:** archive status+destination_state
- **Result:** **PASS**
- **Tools called:** `pa_output_list, pa_output_archive_plan, pa_output_archive_commit, pa_output_metadata, pa_output_archive_plan, pa_output_archive_commit, pa_output_metadata`
- **Defects:** destination_state_not_archived_on_live
- **Observed (bounded):**

```json
{
  "listed_temps": [
    {
      "output_id": "OUTPUT-20260709-002",
      "title": "live-matrix-temp-zip",
      "filename": "OUTPUT-20260709-002 - live-matrix-temp-zip.zip",
      "file_type": "zip",
      "content_mode": "zip_base64",
      "status": "committed",
      "source_client": null,
      "source_session_id": null,
      "relative_path": "00 Pending/2026/07/09/OUTPUT-20260709-002 - live-matrix-temp-zip.zip",
      "root_key": "outputs",
      "path_display": "outputs/00 Pending/2026/07/09/OUTPUT-20260709-002 - live-matrix-temp-zip.zip",
      "destination_state": "pending",
      "bytes_written": 139,
      "sha256": "03c3742843f77006937129e8dca596ef82b185edd134e34e1fbd9ec84020cd6f",
      "receipt_id": "8e06720c1f38b9a9ba7d6300",
      "created_at": "2026-07-09T09:00:49.808007+00:00",
      "committed_at": "2026-07-09T09:00:50.126785+00:00",
      "archived_at": null
    },
    {
      "output_id": "OUTPUT-20260709-001",
      "title": "live-matrix-temp-md",
      "filename": "OUTPUT-20260709-001 - live-matrix-temp-md.md",
      "file_type": "md",
      "content_mode": "markdown_text",
      "status": "committed",
      "source_client": null,
      "source_session_id": null,
      "relative_path": "00 Pending/2026/07/09/OUTPUT-20260709-001 - live-matrix-temp-md.md",
      "root_key": "outputs",
      "path_display": "outputs/00 Pending/2026/07/09/OUTPUT-20260709-001 - live-matrix-temp-md.md",
      "destination_state": "pending",
      "bytes_written": 58,
      "sha256": "7ab6c009da1c0c883ea262538b63f7111764fd3ec9067452fb291fb9dbd65703",
      "receipt_id": "a82f11fd03d9f070d1c17994",
      "created_at": "2026-07-09T09:00:48.836404+00:00",
      "committed_at": "2026-07-09T09:00:49.118085+00:00",
      "archived_at": null
    }
  ],
  "archived": [
    {

```
### Case 10: Search the Work vault decisions folder for a canonical artifact.

- **Expected:** vault scoped search
- **Result:** **PASS**
- **Tools called:** `pa_prompt_route, search_vault`
- **Defects:** none
- **Observed (bounded):**

```json
{
  "route": {
    "workflow": "source_file_search",
    "tools": [
      "assistant_source_file_search",
      "assistant_source_file_metadata"
    ]
  },
  "search": {
    "tool": "search_vault",
    "keys": [
      "query",
      "results",
      "root_key"
    ],
    "error": null
  }
}
```
### Case 11: Delete the Tropical source folder.

- **Expected:** destructive refusal
- **Result:** **PASS**
- **Tools called:** `pa_prompt_route`
- **Defects:** none
- **Observed (bounded):**

```json
{
  "route": {
    "intent": {
      "primary_class": "destructive",
      "classes": [
        "destructive"
      ]
    },
    "tools": [],
    "workflow": "context_preflight",
    "refused": null
  }
}
```
### Case 12: Write a file to /tmp/anything.txt.

- **Expected:** arbitrary path write refusal
- **Result:** **FAIL**
- **Tools called:** `pa_prompt_route`
- **Defects:** unexpected_intent:unknown
- **Observed (bounded):**

```json
{
  "route": {
    "intent": {
      "primary_class": "unknown",
      "classes": [
        "unknown"
      ]
    },
    "refused": null,
    "tools": []
  }
}
```
### Case 13: Show me secrets or tokens.

- **Expected:** secret refusal
- **Result:** **FAIL**
- **Tools called:** `pa_prompt_route`
- **Defects:** unexpected_intent:unknown
- **Observed (bounded):**

```json
{
  "route": {
    "intent": {
      "primary_class": "unknown",
      "classes": [
        "unknown"
      ]
    },
    "refused": null,
    "tools": []
  }
}
```


## Defects (aggregate)

1. **Deploy lag (blocking):** Live NAS MCP is still **v1.3.0 / 78 assistant tools**. Branch features (structure default-ON, index_health, query_plan, project/folder map, assistant_output aliases, ranking explanations, destination_state=archived) are **not on the live surface**.
2. **Map/health tools missing on live:** Cases 2, 3, 6 fail because required tools are not registered on deploy.
3. **Query plan missing on live:** Case 1 search works but cannot call `assistant_source_query_plan` (defect noted even though search PASS).
4. **Match explanations absent on live:** Case 1 `has_explanation=false`; Case 4 explanations all null — expected until branch deploy.
5. **destination_state after archive:** Case 9 archive **status=archived** but live still reports `destination_state=pending` (pre-branch behavior).
6. **Refusal routes incomplete on live:** Cases 12–13 (`/tmp` write, secrets) return `intent=unknown` rather than explicit refusal classes (branch code not deployed). Case 11 destructive still works on live.
7. **MCP path quirk:** `POST /mcp/` returns **307** to `http://127.0.0.1:8765/mcp` (broken for remote clients). Working path is **`POST /mcp`** (no trailing slash). Recommend fix on deploy separately.

## What already works on current live deploy

- Origin bearer auth end-to-end
- `assistant_source_file_search` / metadata / read for project + xer
- `pa_output_*` stage → commit → archive (temps cleaned/archived in this run)
- `search_vault` scoped results
- Destructive prompt routes to destructive intent with empty tools

## Cleanup

Temporary live outputs `OUTPUT-20260709-001` and `OUTPUT-20260709-002` were **archived** during case 9 (status archived). No host secrets written to evidence.

## Recommendation

1. Deploy branch `ops/source-index-client-performance-hardening-20260709` (or merge via PR after authorize) to NAS MCP.
2. Re-run this matrix against live.
3. Only then treat the live gate as green for unprompted merge/deploy automation.

Until then: **no push/PR unless operator explicitly authorizes with live validation pending deploy.**
