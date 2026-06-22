# Forecast Comprehensive — DB-Backed Config Consumer Proof (Phase 20)

- status: not_ready
- decision: not_ready
- not_ready_reason: config_parity_mismatch
- live_db_preflight_stable: True (window 30.0s)
- live_db_unchanged_during_run: True (drift: [])
- live_db_path: /Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite (read-only)
- config_snapshot_id: c3b4a67d22db47c74e696ae562fbf1c555e365fc66bb003a7b3312754415b698
- snapshot_item_count (full): 194
- consumed_config_domains: ['forecast_controls', 'forecast_model_controls', 'project']
- consumed_config_files: ['config/forecast_controls/tropical/code_forecast_controls.jsonl', 'config/forecast_model_controls/tropical/code_forecast_model_controls.jsonl', 'config/projects/tropical.json']
- consumed_snapshot_item_count: 70
- db_backed reads_materialized_config: True
- predecessor_packages.read: ['context', 'cost_frequency', 'crosswalk_v2', 'history_informed', 'intelligence', 'monthly', 'probability', 'schedule_integrated', 'staffing_plan']
- predecessor_packages.generated: []
- standard_comprehensive_package_csvs: ['actuals_monthly_by_budget_code.csv', 'actuals_monthly_by_cost_code.csv', 'actuals_plus_forecast_monthly_by_budget_code.csv', 'actuals_plus_forecast_monthly_by_cost_code.csv']

## Outputs
- file_backed_output_package: /Users/bobbyfetting/hb-personal-assistant/docs/evidence/phase20-forecast-comprehensive-db-config-live-proof/20260620T103706Z/work/file_backed/forecast_comprehensive_package_tropical_20260101_000000
- db_snapshot_backed_output_package: /Users/bobbyfetting/hb-personal-assistant/docs/evidence/phase20-forecast-comprehensive-db-config-live-proof/20260620T103706Z/work/db_snapshot_backed/forecast_comprehensive_package_tropical_20260101_000000

## Parity
- result: fail
- differences: 1
- path_embedding_files (raw-diff confirmed): ['integrated_evidence_registry_by_budget_code.jsonl']
- normalized_rules:
  - raw file-backed vs DB-backed diff inspected (mandatory); only files that embed an absolute config-root/output path are enumerated in _PATH_EMBEDDING_FILES and compared after PATH normalization (<OUTPUT_PACKAGE>/<CONFIG_ROOT>) only
  - integrated_evidence_registry_by_budget_code.jsonl is path-embedded because it records the resolved operator-control source_package_path; ONLY the config-root path token is normalized (its non-path evidence fields — values, weights, signals, lineage — are still compared exactly)
  - NO forecast/actuals/monthly/probability value, row count, warning count, validation status, manifest conclusion, audit/db_inventory.json content, CSV math, source-package lineage, or package-consumption result is ever normalized; standard package CSVs are compared byte-exact

## Differences
  - manifest.json :: validation_report.json.sha256 (file='6aba061c525f44849c5c93f5ae0e02035038eacfffaab0dddfd800d742583cce' db='e6a249edd3020d5dd317e00d8009fb436356a9e813340ef4097e9ce4471c2519')
