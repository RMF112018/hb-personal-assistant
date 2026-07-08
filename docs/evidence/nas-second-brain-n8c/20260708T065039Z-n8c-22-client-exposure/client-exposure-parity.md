# N8C-22 — Client Exposure Parity Audit

- runtime_commit: `v1.3.0`
- canonical assistant tools: **78**
- broker_registered: 78
- status_advertised: 78
- client_manifest_exposed: **78**
- callable_smoke_tested: **78**
- missing_from_client_manifest: 0
- client_bridge_helper_tools: hb_assistant_catalog, hb_assistant_tool_help, hb_assistant_tool_query

**Conclusion:** NO CODE-LEVEL GAP: all 78 canonical assistant tools are broker-registered, status-advertised, present in the live client manifest, and callable through the client wrapper. Any live client-visibility gap is runtime/client-side (stale image, HB_MCP_ASSISTANT_* kill switch, or client tool-count limits), not a missing code layer.

| group | tool_name | broker_registered | status_advertised | server_registered | client_manifest_exposed | callable_smoke_tested | kill_switch | read_only | bounded_result | notes |
|---|---|---|---|---|---|---|---|---|---|---|
| action_stages | assistant_get_action_stage | True | True | True | True | True | HB_MCP_ASSISTANT_ACTION_STAGES | True | True | reachable; fail-closed on synthetic args (stage_not_found) |
| action_stages | assistant_get_action_stage_citations | True | True | True | True | True | HB_MCP_ASSISTANT_ACTION_STAGES | True | True | bounded result via client wrapper |
| action_stages | assistant_get_action_stage_export | True | True | True | True | True | HB_MCP_ASSISTANT_ACTION_STAGES | True | True | reachable; fail-closed on synthetic args (stage_not_found:audit-nonexistent-id) |
| action_stages | assistant_get_action_stage_items | True | True | True | True | True | HB_MCP_ASSISTANT_ACTION_STAGES | True | True | bounded result via client wrapper |
| action_stages | assistant_get_action_stage_summary | True | True | True | True | True | HB_MCP_ASSISTANT_ACTION_STAGES | True | True | bounded result via client wrapper |
| nav | assistant_get_card_for_source | True | True | True | True | True | HB_MCP_ASSISTANT_NAV | True | True | bounded result via client wrapper |
| nav | assistant_get_card_state | True | True | True | True | True | HB_MCP_ASSISTANT_NAV | True | True | bounded result via client wrapper |
| context_packs | assistant_get_context_pack | True | True | True | True | True | HB_MCP_ASSISTANT_CONTEXT_PACKS | True | True | reachable; fail-closed on synthetic args (context_pack_not_found) |
| context_packs | assistant_get_context_pack_items | True | True | True | True | True | HB_MCP_ASSISTANT_CONTEXT_PACKS | True | True | bounded result via client wrapper |
| decision_memory | assistant_get_decision | True | True | True | True | True | HB_MCP_ASSISTANT_DECISION_MEMORY | True | True | reachable; fail-closed on synthetic args (decision_not_found) |
| answer_drafts | assistant_get_draft | True | True | True | True | True | HB_MCP_ASSISTANT_ANSWER_DRAFTS | True | True | reachable; fail-closed on synthetic args (draft_not_found) |
| answer_drafts | assistant_get_draft_citations | True | True | True | True | True | HB_MCP_ASSISTANT_ANSWER_DRAFTS | True | True | bounded result via client wrapper |
| answer_drafts | assistant_get_draft_export | True | True | True | True | True | HB_MCP_ASSISTANT_ANSWER_DRAFTS | True | True | reachable; fail-closed on synthetic args (draft_not_found:audit-nonexistent-id) |
| answer_drafts | assistant_get_draft_sections | True | True | True | True | True | HB_MCP_ASSISTANT_ANSWER_DRAFTS | True | True | bounded result via client wrapper |
| answer_drafts | assistant_get_draft_summary | True | True | True | True | True | HB_MCP_ASSISTANT_ANSWER_DRAFTS | True | True | bounded result via client wrapper |
| review | assistant_get_effective_review_state | True | True | True | True | True | HB_MCP_ASSISTANT_REVIEW | True | True | bounded result via client wrapper |
| feedback | assistant_get_feedback | True | True | True | True | True | HB_MCP_ASSISTANT_FEEDBACK | True | True | reachable; fail-closed on synthetic args (feedback_not_found) |
| feedback | assistant_get_feedback_export | True | True | True | True | True | HB_MCP_ASSISTANT_FEEDBACK | True | True | reachable; fail-closed on synthetic args (feedback_not_found:audit-nonexistent-id) |
| feedback | assistant_get_feedback_recommendations | True | True | True | True | True | HB_MCP_ASSISTANT_FEEDBACK | True | True | bounded result via client wrapper |
| feedback | assistant_get_feedback_summary | True | True | True | True | True | HB_MCP_ASSISTANT_FEEDBACK | True | True | bounded result via client wrapper |
| feedback | assistant_get_feedback_targets | True | True | True | True | True | HB_MCP_ASSISTANT_FEEDBACK | True | True | bounded result via client wrapper |
| intelligence | assistant_get_intelligence_projection | True | True | True | True | True | HB_MCP_ASSISTANT_INTELLIGENCE | True | True | reachable; fail-closed on synthetic args (projection_not_found) |
| intelligence | assistant_get_intelligence_projection_export | True | True | True | True | True | HB_MCP_ASSISTANT_INTELLIGENCE | True | True | reachable; fail-closed on synthetic args (projection_not_found:audit-nonexistent-i) |
| intelligence | assistant_get_intelligence_projection_items | True | True | True | True | True | HB_MCP_ASSISTANT_INTELLIGENCE | True | True | bounded result via client wrapper |
| intelligence | assistant_get_intelligence_summary | True | True | True | True | True | HB_MCP_ASSISTANT_INTELLIGENCE | True | True | bounded result via client wrapper |
| memory | assistant_get_memory_compilations | True | True | True | True | True | HB_MCP_ASSISTANT_MEMORY | True | True | bounded result via client wrapper |
| memory | assistant_get_memory_mentions | True | True | True | True | True | HB_MCP_ASSISTANT_MEMORY | True | True | bounded result via client wrapper |
| memory | assistant_get_memory_node | True | True | True | True | True | HB_MCP_ASSISTANT_MEMORY | True | True | reachable; fail-closed on synthetic args (memory_node_not_found) |
| decision_memory | assistant_get_open_loop | True | True | True | True | True | HB_MCP_ASSISTANT_DECISION_MEMORY | True | True | reachable; fail-closed on synthetic args (open_loop_not_found) |
| decision_memory | assistant_get_preference | True | True | True | True | True | HB_MCP_ASSISTANT_DECISION_MEMORY | True | True | reachable; fail-closed on synthetic args (preference_not_found) |
| quality | assistant_get_quality | True | True | True | True | True | HB_MCP_ASSISTANT_QUALITY | True | True | reachable; fail-closed on synthetic args (quality_run_not_found) |
| quality | assistant_get_quality_export | True | True | True | True | True | HB_MCP_ASSISTANT_QUALITY | True | True | reachable; fail-closed on synthetic args (quality_run_not_found:audit-nonexistent-) |
| quality | assistant_get_quality_findings | True | True | True | True | True | HB_MCP_ASSISTANT_QUALITY | True | True | bounded result via client wrapper |
| quality | assistant_get_quality_summary | True | True | True | True | True | HB_MCP_ASSISTANT_QUALITY | True | True | bounded result via client wrapper |
| quality | assistant_get_quality_targets | True | True | True | True | True | HB_MCP_ASSISTANT_QUALITY | True | True | bounded result via client wrapper |
| nav | assistant_get_related_sources | True | True | True | True | True | HB_MCP_ASSISTANT_NAV | True | True | bounded result via client wrapper |
| research_packets | assistant_get_research_packet | True | True | True | True | True | HB_MCP_ASSISTANT_RESEARCH_PACKETS | True | True | reachable; fail-closed on synthetic args (packet_not_found) |
| research_packets | assistant_get_research_packet_citations | True | True | True | True | True | HB_MCP_ASSISTANT_RESEARCH_PACKETS | True | True | bounded result via client wrapper |
| research_packets | assistant_get_research_packet_export | True | True | True | True | True | HB_MCP_ASSISTANT_RESEARCH_PACKETS | True | True | reachable; fail-closed on synthetic args (packet_not_found:audit-nonexistent-id) |
| research_packets | assistant_get_research_packet_items | True | True | True | True | True | HB_MCP_ASSISTANT_RESEARCH_PACKETS | True | True | bounded result via client wrapper |
| research_packets | assistant_get_research_packet_summary | True | True | True | True | True | HB_MCP_ASSISTANT_RESEARCH_PACKETS | True | True | bounded result via client wrapper |
| review | assistant_get_review_dispositions | True | True | True | True | True | HB_MCP_ASSISTANT_REVIEW | True | True | bounded result via client wrapper |
| review | assistant_get_review_item | True | True | True | True | True | HB_MCP_ASSISTANT_REVIEW | True | True | reachable; fail-closed on synthetic args (review_item_not_found) |
| review | assistant_get_review_summary | True | True | True | True | True | HB_MCP_ASSISTANT_REVIEW | True | True | bounded result via client wrapper |
| nav | assistant_get_source | True | True | True | True | True | HB_MCP_ASSISTANT_NAV | True | True | reachable; fail-closed on synthetic args (source_not_found) |
| nav | assistant_get_source_for_card | True | True | True | True | True | HB_MCP_ASSISTANT_NAV | True | True | bounded result via client wrapper |
| nav | assistant_get_vault_note | True | True | True | True | True | HB_MCP_ASSISTANT_NAV | True | True | reachable; fail-closed on synthetic args (path_not_found) |
| workflows | assistant_get_workflow_artifacts | True | True | True | True | True | HB_MCP_ASSISTANT_WORKFLOWS | True | True | bounded result via client wrapper |
| workflows | assistant_get_workflow_context | True | True | True | True | True | HB_MCP_ASSISTANT_WORKFLOWS | True | True | bounded result via client wrapper |
| workflows | assistant_get_workflow_policy | True | True | True | True | True | HB_MCP_ASSISTANT_WORKFLOWS | True | True | bounded result via client wrapper |
| workflows | assistant_get_workflow_summary | True | True | True | True | True | HB_MCP_ASSISTANT_WORKFLOWS | True | True | bounded result via client wrapper |
| action_stages | assistant_list_action_stages | True | True | True | True | True | HB_MCP_ASSISTANT_ACTION_STAGES | True | True | bounded result via client wrapper |
| nav | assistant_list_ambiguous_card_links | True | True | True | True | True | HB_MCP_ASSISTANT_NAV | True | True | bounded result via client wrapper |
| context_packs | assistant_list_context_packs | True | True | True | True | True | HB_MCP_ASSISTANT_CONTEXT_PACKS | True | True | bounded result via client wrapper |
| decision_memory | assistant_list_decisions | True | True | True | True | True | HB_MCP_ASSISTANT_DECISION_MEMORY | True | True | bounded result via client wrapper |
| answer_drafts | assistant_list_drafts | True | True | True | True | True | HB_MCP_ASSISTANT_ANSWER_DRAFTS | True | True | bounded result via client wrapper |
| nav | assistant_list_duplicate_cards | True | True | True | True | True | HB_MCP_ASSISTANT_NAV | True | True | bounded result via client wrapper |
| context_packs | assistant_list_enrichment_review_items | True | True | True | True | True | HB_MCP_ASSISTANT_CONTEXT_PACKS | True | True | bounded result via client wrapper |
| feedback | assistant_list_feedback | True | True | True | True | True | HB_MCP_ASSISTANT_FEEDBACK | True | True | bounded result via client wrapper |
| intelligence | assistant_list_intelligence_projections | True | True | True | True | True | HB_MCP_ASSISTANT_INTELLIGENCE | True | True | bounded result via client wrapper |
| memory | assistant_list_memory_nodes | True | True | True | True | True | HB_MCP_ASSISTANT_MEMORY | True | True | bounded result via client wrapper |
| decision_memory | assistant_list_open_loops | True | True | True | True | True | HB_MCP_ASSISTANT_DECISION_MEMORY | True | True | bounded result via client wrapper |
| decision_memory | assistant_list_preferences | True | True | True | True | True | HB_MCP_ASSISTANT_DECISION_MEMORY | True | True | bounded result via client wrapper |
| quality | assistant_list_quality | True | True | True | True | True | HB_MCP_ASSISTANT_QUALITY | True | True | bounded result via client wrapper |
| research_packets | assistant_list_research_packets | True | True | True | True | True | HB_MCP_ASSISTANT_RESEARCH_PACKETS | True | True | bounded result via client wrapper |
| review | assistant_list_review_items | True | True | True | True | True | HB_MCP_ASSISTANT_REVIEW | True | True | bounded result via client wrapper |
| nav | assistant_list_stale_cards | True | True | True | True | True | HB_MCP_ASSISTANT_NAV | True | True | bounded result via client wrapper |
| workflows | assistant_list_workflows | True | True | True | True | True | HB_MCP_ASSISTANT_WORKFLOWS | True | True | bounded result via client wrapper |
| nav | assistant_recent_changes | True | True | True | True | True | HB_MCP_ASSISTANT_NAV | True | True | bounded result via client wrapper |
| workflows | assistant_route_workflow | True | True | True | True | True | HB_MCP_ASSISTANT_WORKFLOWS | True | True | bounded result via client wrapper |
| nav | assistant_search_cards | True | True | True | True | True | HB_MCP_ASSISTANT_NAV | True | True | bounded result via client wrapper |
| nav | assistant_search_sources | True | True | True | True | True | HB_MCP_ASSISTANT_NAV | True | True | bounded result via client wrapper |
| source_connector | assistant_source_file_metadata | True | True | True | True | True | HB_MCP_ASSISTANT_SOURCE_CONNECTOR | True | True | reachable; fail-closed on synthetic args (source_id_or_ref_required) |
| source_connector | assistant_source_file_read | True | True | True | True | True | HB_MCP_ASSISTANT_SOURCE_CONNECTOR | True | True | reachable; fail-closed on synthetic args (source_id_or_ref_required) |
| source_connector | assistant_source_file_search | True | True | True | True | True | HB_MCP_ASSISTANT_SOURCE_CONNECTOR | True | True | bounded result via client wrapper |
| source_connector | assistant_source_files_list | True | True | True | True | True | HB_MCP_ASSISTANT_SOURCE_CONNECTOR | True | True | bounded result via client wrapper |
| source_connector | assistant_source_roots_list | True | True | True | True | True | HB_MCP_ASSISTANT_SOURCE_CONNECTOR | True | True | bounded result via client wrapper |
| source_connector | assistant_source_status | True | True | True | True | True | HB_MCP_ASSISTANT_SOURCE_CONNECTOR | True | True | bounded result via client wrapper |
