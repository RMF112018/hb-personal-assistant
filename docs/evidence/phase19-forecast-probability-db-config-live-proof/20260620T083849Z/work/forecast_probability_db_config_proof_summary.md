# Forecast Probability — DB-Backed Config Consumer Proof (Phase 19)

- status: ready
- decision: forecast_probability_db_config_parity_ready
- not_ready_reason: None
- live_db_preflight_stable: True (window 30.0s)
- live_db_unchanged_during_run: True (drift: [])
- live_db_path: /Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite (read-only)
- config_snapshot_id: c3b4a67d22db47c74e696ae562fbf1c555e365fc66bb003a7b3312754415b698
- snapshot_item_count (full): 194
- consumed_config_domains: ['owner_sov_crosswalk', 'project']
- consumed_config_files: ['config/crosswalks/tropical/owner_sov_scope_crosswalk_tropical_authoritative_20260614_final.jsonl', 'config/projects/tropical.json']
- consumed_snapshot_item_count: 59
- probability_run: {'runs': 10000, 'seed': 20260614, 'forecast_start_month': None}

## Outputs
- file_backed_output_package: /Users/bobbyfetting/hb-personal-assistant/docs/evidence/phase19-forecast-probability-db-config-live-proof/20260620T083849Z/work/file_backed/forecast_probability_package_tropical_20260101_000000
- db_snapshot_backed_output_package: /Users/bobbyfetting/hb-personal-assistant/docs/evidence/phase19-forecast-probability-db-config-live-proof/20260620T083849Z/work/db_snapshot_backed/forecast_probability_package_tropical_20260101_000000

## Parity
- result: pass
- differences: 0
- path_embedding_files (raw-diff confirmed): []
- normalized_rules:
  - raw file-backed vs DB-backed diff inspected; forecast_probability embeds no consumed-config path in its outputs, so the path-embedding set is EMPTY and every file is compared byte-exact
  - NO probability/monthly value, row count, warning count, validation status, manifest conclusion, audit/db_inventory.json content, or any financial/math output is ever normalized
