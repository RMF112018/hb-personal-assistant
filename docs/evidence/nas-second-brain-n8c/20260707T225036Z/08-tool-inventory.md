# N8C-20 — MCP tool inventory (13 read-only assistant groups / 78 tools)

| # | group | gate (`profile.py`) | env kill-switch | tools |
|---|-------|---------------------|-----------------|-------|
| 1 | nav | `assistant_nav_enabled` | `HB_MCP_ASSISTANT_NAV` | 12 |
| 2 | context_packs | `assistant_context_packs_enabled` | `HB_MCP_ASSISTANT_CONTEXT_PACKS` | 4 |
| 3 | memory | `assistant_memory_enabled` | `HB_MCP_ASSISTANT_MEMORY` | 4 |
| 4 | decision_memory | `assistant_decision_memory_enabled` | `HB_MCP_ASSISTANT_DECISION_MEMORY` | 6 |
| 5 | review | `assistant_review_enabled` | `HB_MCP_ASSISTANT_REVIEW` | 5 |
| 6 | intelligence | `assistant_intelligence_enabled` | `HB_MCP_ASSISTANT_INTELLIGENCE` | 5 |
| 7 | research_packets | `assistant_research_packets_enabled` | `HB_MCP_ASSISTANT_RESEARCH_PACKETS` | 6 |
| 8 | source_connector | `assistant_source_connector_enabled` | `HB_MCP_ASSISTANT_SOURCE_CONNECTOR` | 6 |
| 9 | answer_drafts | `assistant_answer_drafts_enabled` | `HB_MCP_ASSISTANT_ANSWER_DRAFTS` | 6 |
| 10 | workflows | `assistant_workflows_enabled` | `HB_MCP_ASSISTANT_WORKFLOWS` | 6 |
| 11 | feedback | `assistant_feedback_enabled` | `HB_MCP_ASSISTANT_FEEDBACK` | 6 |
| 12 | action_stages | `assistant_action_stages_enabled` | `HB_MCP_ASSISTANT_ACTION_STAGES` | 6 |
| **13** | **quality** | **`assistant_quality_enabled`** | **`HB_MCP_ASSISTANT_QUALITY`** | **6** |

Assistant tool total: **72 → 78** (+6 quality). Live count verified against a fresh registration:
`ASSISTANT_TOOLS 78`, `QUALITY_TOOLS 6`. Each group is independently gated (default-ON); disabling
`HB_MCP_ASSISTANT_QUALITY` denies only the six quality tools and leaves all sibling groups enabled.

The quality group's six tools (all read-only, all clear the finality guard):

```
assistant_list_quality              list persisted quality runs
assistant_get_quality               one run header
assistant_get_quality_findings      a run's advisory findings
assistant_get_quality_targets       the run's evaluated target(s)
assistant_get_quality_summary       bounded aggregate (by kind/status/finding-type/severity)
assistant_get_quality_export        bounded JSON export (header + findings + targets)
```

`hb_mcp_status` aggregates all 13 groups' `*_enabled` + `*_tools`. `ai_outputs_card_upsert` remains the only
sanctioned remote write.
