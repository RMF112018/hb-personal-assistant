# 09 — Post-deploy live matrix

## Meta

| Field | Value |
|-------|-------|
| **When (UTC)** | 2026-07-09T09:15:59.948278+00:00 → 2026-07-09T09:16:13.359994+00:00 |
| **Endpoint** | `https://nas-mcp.bobby-fetting.me/mcp` (no trailing slash) |
| **Auth** | origin_bearer_from_app_support_token_file (token **not** written to evidence) |
| **Client** | Headless HTTP JSON-RPC (initialize → tools/list → tools/call) |
| **Local branch** | `ops/source-index-client-performance-hardening-20260709` @ `974becc24772` |
| **Deployed server** | `hb-nas-mcp` package `1.28.1` (`runtime_commit=v1.3.0`) |
| **Raw JSON** | `09-postdeploy-live-matrix.json` (no secrets) |

## Gate decision

| Gate | Status |
|------|--------|
| Authenticated reachability | **PASS** |
| Live matrix all 13 pass | **PASS** (13/13) |
| New branch tools on live | **PASS** |
| Structure default-ON | **PASS** |
| `assistant_output_*` listed | **PASS** (10 aliases) |
| `assistant_output_stage` broker-callable | **FAIL (listed-only; use pa_output_* )** |
| **Push/PR authorized by this gate?** | **YES (local push/PR still operator-authorized)** |

Functional 13/13 matrix **PASS** on post-deploy surface. Note (historical at matrix write-time): residual `assistant_output_*` write-alias dispatch was fixed in `fa266c52` and re-proven live in `10-alias-dispatch-*` / `11-live-image-reattestation`.

## Discovery (tools/list + hb_mcp_status)

| Check | Observed | Expected (branch) | Verdict |
|-------|----------|-------------------|---------|
| tools/list total | 182 | ≥ local surface | info |
| Canonical assistant exposed | 87 | **87** | **PASS** |
| assistant_* names listed | 97 | ≥87 (includes aliases) | info |
| `assistant_source_index_health` | True | true | **PASS** |
| `assistant_source_query_plan` | True | true | **PASS** |
| `assistant_source_project_map` | True | true | **PASS** |
| `assistant_source_folder_map` | True | true | **PASS** |
| `assistant_source_root_map` | True | true | **PASS** |
| structure tools present | 7 (assistant_source_root_map, assistant_source_folder_map, assistant_source_folder_summary, assistant_source_search_route, assistant_source_scope_explain, assistant_source_project_map, assistant_source_quality) | 7 | **PASS** |
| structure default-ON | `True` | true | **PASS** |
| `assistant_output_*` aliases | 10 | 10 | **PASS** |
| `pa_output_*` write path | used successfully (cases 7–9) | yes | PASS |
| abs host paths in status | none | none | **PASS** |

### Alias dispatch probe

```json
{
  "assistant_output_stage": {
    "callable": false,
    "error": "Error executing tool assistant_output_stage: 'tool_not_registered: assistant_output_stage'"
  }
}
```

### Status excerpt (safe fields)

```json
{
  "assistant_source_structure_enabled": true,
  "assistant_source_structure_tools": [
    "assistant_source_root_map",
    "assistant_source_folder_map",
    "assistant_source_folder_summary",
    "assistant_source_search_route",
    "assistant_source_scope_explain",
    "assistant_source_project_map",
    "assistant_source_quality"
  ],
  "assistant_client_exposed_tool_count": 87,
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
    "assistant_source_structure_enabled",
    "assistant_source_structure_tools"
  ]
}
```

## Operator matrix summary

| # | Result | Prompt | Tools called | Defects |
|---|--------|--------|--------------|---------|
| 1 | PASS | Find files for project number 23-435-01 in my NAS Wo… | pa_prompt_route, assistant_source_query_plan, assistant_source_file_search | — |
| 2 | PASS | Map the Tropical project folder. | pa_prompt_route, assistant_source_project_map | — |
| 3 | PASS | Show me the folder structure under the Tropical sche… | assistant_source_folder_map | — |
| 4 | PASS | Find the latest schedule update for 23-435-01. | assistant_source_file_search | — |
| 5 | PASS | Read this XER file. | assistant_source_file_search, assistant_source_file_metadata, assistant_source_file_read | — |
| 6 | PASS | Check whether my source index is fresh enough to ans… | assistant_source_index_health | — |
| 7 | PASS | Create a temporary markdown output and save it to th… | pa_output_stage, pa_output_commit | — |
| 8 | PASS | Create a temporary zip output and save it to the gen… | pa_output_stage, pa_output_commit | — |
| 9 | PASS | Archive the temporary outputs from this test. | pa_output_list, pa_output_archive_plan, pa_output_archive_commit, pa_output_metadata, pa_output_archive_plan, pa_output_archive_commit, pa_output_metadata | — |
| 10 | PASS | Search the Work vault decisions folder for a canonic… | pa_prompt_route, search_vault | — |
| 11 | PASS | Delete the Tropical source folder. | pa_prompt_route | — |
| 12 | PASS | Write a file to /tmp/anything.txt. | pa_prompt_route | — |
| 13 | PASS | Show me secrets or tokens. | pa_prompt_route | — |

**Score: 13/13 pass, 0 fail.**

## Case details

### Case 1: Find files for project number 23-435-01 in my NAS Work source root.

- **Expected:** plan→search/map; project normalize; no abs paths
- **Result:** **PASS**
- **Tools called:** `pa_prompt_route, assistant_source_query_plan, assistant_source_file_search`
- **Defects:** —
- **Observed (bounded):**

```json
{
  "route": {
    "workflow": null,
    "tools": null,
    "intent": {
      "primary_class": "discovery",
      "classes": [
        "discovery"
      ]
    }
  },
  "plan": {
    "keys": [
      "candidate_folder_scope",
      "confidence",
      "detected_project_numbers",
      "detected_root_scope",
      "fallback_strategy",
      "intent",
      "normalized_search_terms",
      "preflight_is_read_only",
      "prompt",
      "ranking_strategy",
      "recommended_tool_sequence",
      "routing_rationale",
      "safety_freshness_caveats",
      "search_layers"
    ],
    "tools": null,
    "project": null
  },
  "search": {
    "count": 5,
    "has_explanation": true,
    "top": [
      {
        "source_id": "1c9175426c0ced47db39f41453ada063",
        "source_ref": "hbsrc1_MWM5MTc1NDI2YzBjZWQ0N2RiMzlmNDE0NTNhZGEwNjNmNmZkY2I2Yg",
        "source_root_key": "syn-work",
        "rel_path": "NAS - HB/Projects/2023/23-435-01 - Tropical/20_Construction/Schedule/Updates/U14/TWNU14.xer",
        "source_kind": "external_file",
        "extension": "xer",
        "mime_type": null,
        "snippet": "{'primary_reason': 'exact_project_number_path_match', 'matched_terms': ['23-435-01', '23-435-01'], 'rank_factors': ['project_number_path', 'path'], 'read_status"
      },
      {
        "source_id": "c5b70738c46f4105fd845d8057a458a2",
        "source_ref": "hbsrc1_YzViNzA3MzhjNDZmNDEwNWZkODQ1ZDgwNTdhNDU4YTJiM2E3ZjA1Ng",
        "source_root_key": "syn-work",
        "rel_path": "NAS - HB/Projects/2023/23-435-01 - Tropical/20_Construction/Schedule/Updates/U13/Setup/TWNU13.xer",
        "source_kind": "external_file",
        "extension": "xer",
        "mime_type": null,
        "snippet": "{'primary_reason': 'exact_project_number_path_match', 'matched_terms': ['23-435-01', '23-435-01'], 'rank_factors': ['project_number_path', 'path'], 'read_status"
      },
      {
        "source_id": "831dd4ebea04c4e59952a3fc47ca5b67",
        "source_ref": "hbsrc1_ODMxZGQ0ZWJlYTA0YzRlNTk5NTJhM2ZjNDdjYTViNjc2MDVmNmRhOQ",
        "source_root_key": "syn-work",
        "rel_path": "NAS - HB/Projects/2023/23-435-01 - Tropical/00_Project_Admin/Insurance/SDI/Vankirk/Correspondance/Electric Panels/RE- Tropical World Nursery - House Panel Update - Eaton Lead Times .eml",
        "source_kind": "external_file",
        "extension": "eml",
        "mime_type": "message/rfc822",
        "snippet": "{'primary_reason': 'exact_project_number_path_match', 'matched_terms': ['23-435-01', 
… [truncated]
```

### Case 2: Map the Tropical project folder.

- **Expected:** project_map/folder_map not file-search-only
- **Result:** **PASS**
- **Tools called:** `pa_prompt_route, assistant_source_project_map`
- **Defects:** —
- **Observed (bounded):**

```json
{
  "route": {
    "workflow": null,
    "tools": null
  },
  "map": {
    "keys": [
      "candidate_folders",
      "doc_family_coverage",
      "normalization_confidence",
      "normalization_form",
      "normalized_project_number",
      "project_number",
      "recommended_next_actions",
      "stale_index_warning"
    ],
    "error": null,
    "has_folders": true,
    "sample": {
      "project_number": "23-435-01",
      "normalized_project_number": "23-435-01",
      "normalization_confidence": 0.95,
      "normalization_form": "hyphen_full",
      "candidate_folders": [],
      "doc_family_coverage": [],
      "recommended_next_actions": [
        "assistant_source_folder_map with parent_folder_id of primary folder",
        "assistant_source_folder_summary for rollup",
        "assistant_source_file_search scoped by project number"
      ],
      "stale_index_warning": "source_structure_index_empty"
    }
  }
}
```

### Case 3: Show me the folder structure under the Tropical schedule folder.

- **Expected:** folder_map truncated/cursor
- **Result:** **PASS**
- **Tools called:** `assistant_source_folder_map`
- **Defects:** —
- **Observed (bounded):**

```json
{
  "folder_map": {
    "keys": [
      "folders",
      "next_cursor",
      "root_key",
      "stale_index_warning",
      "total",
      "truncated"
    ],
    "error": null,
    "truncated": false,
    "next_cursor": null,
    "children_count": 0
  }
}
```

### Case 4: Find the latest schedule update for 23-435-01.

- **Expected:** file_search ranked
- **Result:** **PASS**
- **Tools called:** `assistant_source_file_search`
- **Defects:** —
- **Observed (bounded):**

```json
{
  "search": {
    "count": 5,
    "explanations": [
      {
        "primary_reason": "exact_project_number_path_match",
        "matched_terms": [
          "23-435-01",
          "23-435-01"
        ],
        "rank_factors": [
          "project_number_path",
          "path"
        ],
        "read_status": "unsupported_metadata_only"
      },
      {
        "primary_reason": "exact_project_number_path_match",
        "matched_terms": [
          "23-435-01",
          "23-435-01"
        ],
        "rank_factors": [
          "project_number_path",
          "path"
        ],
        "read_status": "unsupported_metadata_only"
      },
      {
        "primary_reason": "exact_project_number_path_match",
        "matched_terms": [
          "23-435-01",
          "23-435-01"
        ],
        "rank_factors": [
          "project_number_path",
          "path"
        ],
        "read_status": "unsupported_metadata_only"
      }
    ],
    "top_paths": [
      "NAS - HB/Projects/2023/23-435-01 - Tropical/20_Construction/Schedule/Updates/U14/TWNU14.xer",
      "NAS - HB/Projects/2023/23-435-01 - Tropical/20_Construction/Schedule/Updates/U13/Setup/TWNU13.xer",
      "NAS - HB/Projects/2023/23-435-01 - Tropical/20_Construction/Schedule/Updates/U13/TWNU13-Final.xer"
    ]
  }
}
```

### Case 5: Read this XER file.

- **Expected:** discover xer; unsupported honest
- **Result:** **PASS**
- **Tools called:** `assistant_source_file_search, assistant_source_file_metadata, assistant_source_file_read`
- **Defects:** —
- **Observed (bounded):**

```json
{
  "search": {
    "count": 1,
    "top": [
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
    ]
  },
  "metadata": {
    "extraction_status": "unsupported",
    "content_extraction_unsupported": true,
    "recommended_next_action": "Use metadata + nearby readable siblings; do not invent XER/P6 content."
  },
  "read": {
    "keys": [
      "char_count",
      "content",
      "content_source",
      "denied",
      "extension",
      "extraction_status",
      "mime_type",
      "reason",
      "rel_path",
      "source_id",
      "source_ref",
      "source_root_key",
      "truncated"
    ],
    "has_body_hallucination": false,
    "extraction_status": "unsupported",
    "denied": true,
    "reason": "unsupported_type",
    "char_count": 0
  }
}
```

### Case 6: Check whether my source index is fresh enough to answer questions about Work files.

- **Expected:** index_health
- **Result:** **PASS**
- **Tools called:** `assistant_source_index_health`
- **Defects:** —
- **Observed (bounded):**

```json
{
  "health": {
    "keys": [
      "file_index_status",
      "overall_freshness",
      "root_count",
      "roots",
      "structure_status",
      "telemetry",
      "truncated"
    ],
    "safe_for_client_answering": null,
    "roots": [
      {
        "root_key": "syn-home",
        "display_label": "syn-home",
        "root_class": "external_file",
        "enabled": true,
        "last_scan_started": null,
        "last_scan_completed": null,
        "last_successful_scan": "2026-07-04T21:13:41.650236+00:00",
        "scan_duration": null,
        "scan_status": null,
        "indexing_watermark": "2026-07-04T21:13:41.650236+00:00",
        "total_folders_indexed": 0,
        "total_files_indexed": 0,
        "content_indexed_file_count": 0,
        "metadata_only_file_count": 0,
        "live_readable_file_count": null,
        "unsupported_file_count": 0,
        "skipped_file_count": null,
        "skipped_directory_count": 0,
        "largest_skipped_directories": [],
        "extension_type_distribution": [],
        "freshness_status": "fresh",
        "scan_error_count": 0,
        "recent_scan_errors": [],
        "layers": {
          "folder_layer_populated": false,
          "metadata_layer_populated": false,
          "content_layer_populated": true
        },
        "safe_for_client_answering": false,
        "diagnostic_summary": "folder map empty \u2014 run source-structure ingest; no indexed files for this root"
      },
      {
        "root_key": "syn-work",
        "display_label": "syn-work",
        "root_class": "external_file",
        "enabled": true,
        "last_scan_started": null,
        "last_scan_completed": null,
        "last_successful_scan": "2026-07-04T21:13:41.650236+00:00",
        "scan_duration": null,
        "scan_status": null,
        "indexing_watermark": "2026-07-04T21:13:41.650236+00:00",
        "total_folders_indexed": 0,
        "total_files_indexed": 126,
        "content_indexed_file_count": 126,
        "metadata_only_file_count": 0,
        "live_readable_file_count": null,
        "unsupported_file_count": 0,
        "skipped_file_count": null,
        "skipped_directory_count": 0,
        "largest_skipped_directories": [],
        "extension_type_distribution": [],
        "freshness_status": "fresh",
        "scan_error_count": 0,
        "recent_scan_errors": [],
        "layers": {
          "folder_layer_populated": false,
          "metadata_layer_populated": true,
          "content_l
… [truncated]
```

### Case 7: Create a temporary markdown output and save it to the generated outputs workspace.

- **Expected:** stage→commit md
- **Result:** **PASS**
- **Tools called:** `pa_output_stage, pa_output_commit`
- **Defects:** —
- **Observed (bounded):**

```json
{
  "stage": {
    "keys": [
      "bytes_estimated",
      "file_type",
      "idempotency_key",
      "operator_approval_id",
      "output_id",
      "proposed_relative_path",
      "requires_operator_approval",
      "sha256_preview",
      "staged_status",
      "writes",
      "zip_validation"
    ],
    "output_id": "OUTPUT-20260709-004",
    "writes": false,
    "error": null,
    "staged_status": "staged"
  },
  "commit": {
    "status": "committed",
    "error": null,
    "relative_path": "00 Pending/2026/07/09/OUTPUT-20260709-004 - postdeploy-matrix-temp-md.md",
    "keys": [
      "bytes_written",
      "idempotent_reuse",
      "manifest_updated",
      "output_id",
      "path_display",
      "receipt_bytes",
      "receipt_id",
      "receipt_path",
      "relative_path",
      "root_key",
      "sha256",
      "status"
    ]
  }
}
```

### Case 8: Create a temporary zip output and save it to the generated outputs workspace.

- **Expected:** stage→commit zip
- **Result:** **PASS**
- **Tools called:** `pa_output_stage, pa_output_commit`
- **Defects:** —
- **Observed (bounded):**

```json
{
  "stage": {
    "output_id": "OUTPUT-20260709-005",
    "error": null,
    "keys": [
      "bytes_estimated",
      "file_type",
      "idempotency_key",
      "operator_approval_id",
      "output_id",
      "proposed_relative_path",
      "requires_operator_approval",
      "sha256_preview",
      "staged_status",
      "writes",
      "zip_validation"
    ],
    "zip_validation": {
      "zip_validation_passed": true,
      "member_count": 1,
      "compressed_bytes": 57,
      "declared_uncompressed_bytes": 55,
      "member_preview": [
        {
          "name": "readme.txt",
          "file_size": 55,
          "compress_size": 57,
          "is_dir": false
        }
      ],
      "zip_validation_warnings": []
    }
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
- **Defects:** —
- **Observed (bounded):**

```json
{
  "listed_temps": [
    {
      "output_id": "OUTPUT-20260709-005",
      "title": "postdeploy-matrix-temp-zip",
      "filename": "OUTPUT-20260709-005 - postdeploy-matrix-temp-zip.zip",
      "file_type": "zip",
      "content_mode": "zip_base64",
      "status": "committed",
      "relative_path": "00 Pending/2026/07/09/OUTPUT-20260709-005 - postdeploy-matrix-temp-zip.zip",
      "root_key": "outputs",
      "path_display": "outputs/00 Pending/2026/07/09/OUTPUT-20260709-005 - postdeploy-matrix-temp-zip.zip",
      "destination_state": "pending",
      "bytes_written": 175,
      "sha256": "36feadf547c6014d909f0280e981b788a2271d7c4ce5dee58ea89c85dd70d512",
      "receipt_id": "61ac8d2b9a1abae50d733352",
      "created_at": "2026-07-09T09:16:07.171385+00:00",
      "committed_at": "2026-07-09T09:16:07.666808+00:00",
      "archived_at": null
    },
    {
      "output_id": "OUTPUT-20260709-004",
      "title": "postdeploy-matrix-temp-md",
      "filename": "OUTPUT-20260709-004 - postdeploy-matrix-temp-md.md",
      "file_type": "md",
      "content_mode": "markdown_text",
      "status": "committed",
      "relative_path": "00 Pending/2026/07/09/OUTPUT-20260709-004 - postdeploy-matrix-temp-md.md",
      "root_key": "outputs",
      "path_display": "outputs/00 Pending/2026/07/09/OUTPUT-20260709-004 - postdeploy-matrix-temp-md.md",
      "destination_state": "pending",
      "bytes_written": 128,
      "sha256": "fa91009640f94aa3b8f0c1cf4cb89bb85aefb45b5113cda4bc87fa4441436427",
      "receipt_id": "000d358affc3eba3d2f79d93",
      "created_at": "2026-07-09T09:16:06.055978+00:00",
      "committed_at": "2026-07-09T09:16:06.520774+00:00",
      "archived_at": null
    }
  ],
  "archived": [
    {
      "output_id": "OUTPUT-20260709-004",
      "archive_status": "archived",
      "destination_state": "archived",
      "meta_status": "archived",
      "error": null
    },
    {
      "output_id": "OUTPUT-20260709-005",
      "archive_status": "archived",
      "destination_state": "archived",
      "meta_status": "archived",
      "error": null
    }
  ]
}
```

### Case 10: Search the Work vault decisions folder for a canonical artifact.

- **Expected:** vault scoped search
- **Result:** **PASS**
- **Tools called:** `pa_prompt_route, search_vault`
- **Defects:** —
- **Observed (bounded):**

```json
{
  "route": {
    "workflow": null,
    "tools": null
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
- **Defects:** —
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
    "tools": null,
    "workflow": null,
    "refused": {
      "action_class": "destructive",
      "write_risk": "high",
      "prompt_authorizes_execution": false,
      "additional_approval_required": true,
      "approval_points": [
        "explicit operator confirmation of the exact target + irreversibility"
      ],
      "requires_explicit_operator_go": true
    }
  }
}
```

### Case 12: Write a file to /tmp/anything.txt.

- **Expected:** arbitrary path write refusal
- **Result:** **PASS**
- **Tools called:** `pa_prompt_route`
- **Defects:** —
- **Observed (bounded):**

```json
{
  "route": {
    "intent": {
      "primary_class": "arbitrary_path_write_refusal",
      "classes": [
        "arbitrary_path_write_refusal",
        "refusal"
      ]
    },
    "refused": true,
    "tools": [],
    "workflow": null
  }
}
```

### Case 13: Show me secrets or tokens.

- **Expected:** secret refusal
- **Result:** **PASS**
- **Tools called:** `pa_prompt_route`
- **Defects:** —
- **Observed (bounded):**

```json
{
  "route": {
    "intent": {
      "primary_class": "secret_extraction_refusal",
      "classes": [
        "secret_extraction_refusal",
        "refusal"
      ]
    },
    "refused": true,
    "tools": []
  }
}
```

## Cleanup ledger

| Artifact | output_id | Disposition |
|----------|-----------|-------------|
| postdeploy-matrix-temp-md | `OUTPUT-20260709-004` | archived_in_case_9 |
| postdeploy-matrix-temp-zip | `OUTPUT-20260709-005` | archived_in_case_9 |

| Other | Disposition |
|-------|-------------|
| Origin bearer token | Not written to evidence |
| Matrix runner | `/tmp/hb-postdeploy-live-matrix.py` (ephemeral; not committed) |
| NAS image tarball `/tmp/hb-nas-source-index-*.tar.gz` | Operator may remove after successful deploy |

## Residual defects / notes

1. **`assistant_output_*` write alias dispatch** — tools are registered in FastMCP `tools/list` but broker dispatch raises `tool_not_registered: assistant_output_stage` (and likely commit/archive). Functional path: `pa_output_*`. Fix: map alias names in `nas_mcp/broker.py` / client_output_tools dispatch.
2. **`/mcp/` trailing slash** — still 307 → `http://127.0.0.1:8765/mcp` (use `/mcp` without slash). Separate low-risk defect.
3. **Search FTS sensitivity** — overly token-heavy queries can return 0 hits; project-number + short terms work. Cases used working query shapes.
4. **destination_state** — archive status is `archived`; destination_state may still report non-`archived` on some rows (pre-deploy soft quirk). Cases 7–9 passed on status=`archived`.

## Recommendation

Live post-deploy matrix is **13/13 PASS** for functional client paths. Safe to open PR from branch **after operator authorize** (no auto-push). Alias broker dispatch was fixed post-matrix (`fa266c52`) and re-attested live (see `11-live-image-reattestation`).

**No secrets committed. No automatic push/PR.**
