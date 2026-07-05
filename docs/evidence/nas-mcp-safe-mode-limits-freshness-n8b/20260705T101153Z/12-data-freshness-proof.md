# 12 — Data Freshness Proof

| requirement | test | result |
|---|---|---|
| present data reported | `test_freshness_reports_present_and_missing_explicitly` | schema_version `{ok, version:99, applied_at}` |
| missing data explicit | same | daily_brief `not_configured` (absent table) |
| watcher unknown on NAS | same | watcher `{status: unknown, note: not_available_on_nas}` |
| source-intel counts | same | error_count 1 from seeded events |
| no local path leak | `test_freshness_output_has_no_local_paths` | db_path + vault mount absent from serialized output |
| requires origin auth | `test_freshness_requires_origin_auth` | 401 without bearer; 200 with valid bearer (end-to-end app) |
| allowed in safe mode | `test_safe_mode_allows_status_and_freshness` | hb_data_freshness ok under HB_MCP_SAFE_MODE=1 |
| Tier 0 in audit | `test_freshness_tier0_in_audit` | audit `capability_tier == 0`, decision allow |
