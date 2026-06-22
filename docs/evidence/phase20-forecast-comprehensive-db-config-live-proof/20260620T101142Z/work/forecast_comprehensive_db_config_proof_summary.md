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
- file_backed_output_package: /Users/bobbyfetting/hb-personal-assistant/docs/evidence/phase20-forecast-comprehensive-db-config-live-proof/20260620T101142Z/work/file_backed/forecast_comprehensive_package_tropical_20260101_000000
- db_snapshot_backed_output_package: /Users/bobbyfetting/hb-personal-assistant/docs/evidence/phase20-forecast-comprehensive-db-config-live-proof/20260620T101142Z/work/db_snapshot_backed/forecast_comprehensive_package_tropical_20260101_000000

## Parity
- result: fail
- differences: 5
- path_embedding_files (raw-diff confirmed): []
- normalized_rules:
  - raw file-backed vs DB-backed diff inspected (mandatory); only files that embed an absolute config-root/output path are enumerated in _PATH_EMBEDDING_FILES and compared after PATH normalization (<OUTPUT_PACKAGE>/<CONFIG_ROOT>) only
  - NO forecast/monthly/probability value, row count, warning count, validation status, manifest conclusion, audit/db_inventory.json content, CSV math, source-package lineage, or package-consumption result is ever normalized; standard package CSVs are compared byte-exact

## Differences
  - integrated_evidence_registry_by_budget_code.jsonl :: <bytes> (file='7b3068b347e04d56b09814857d0f3f233664aa6421c8b6de2e02bf08c35258af' db='bb15c03f4ddd06c540afd21d4cae2937da8c33e72f33a89ebdf4529f1181db72')
  - validation_report.json :: <normalized-text> (file='-        "sha256": "7b3068b347e04d56b09814857d0f3f233664aa6421c8b6de2e02bf08c35258af",' db='<see file value>')
  - manifest.json :: integrated_evidence_registry_by_budget_code.jsonl.size_bytes (file=1789001 db=1794633)
  - manifest.json :: integrated_evidence_registry_by_budget_code.jsonl.sha256 (file='7b3068b347e04d56b09814857d0f3f233664aa6421c8b6de2e02bf08c35258af' db='bb15c03f4ddd06c540afd21d4cae2937da8c33e72f33a89ebdf4529f1181db72')
  - manifest.json :: validation_report.json.sha256 (file='6aba061c525f44849c5c93f5ae0e02035038eacfffaab0dddfd800d742583cce' db='b045d9b8975b5f54228c02524d8803c196ffd2ad4f6903f7ccb6550508297fe1')
