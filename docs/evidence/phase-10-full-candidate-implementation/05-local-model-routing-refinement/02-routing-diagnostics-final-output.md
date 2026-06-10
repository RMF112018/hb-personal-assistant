# Local Model Routing Diagnostics

_daemon reachable: True · present models: llama3.1:8b, mistral-nemo:12b, qwen2.5:14b · heavy enabled: False_

## Summary
- task families: 7 · available: 7 · blocked (fail-closed): 0 · fallback-selected: 0

## Per task family
- **calendar_prep_summary** → selected `default_extract` (mistral-nemo:12b) · reason `selected_routed` · safety `redacted_advisory` · no-cloud True
  - chain: default_extract(mistral-nemo:12b):available
- **daily_brief_synthesis_quality** → selected `brief_synthesis` (mistral-nemo:12b) · reason `selected_routed` · safety `redacted_advisory` · no-cloud True
  - chain: brief_synthesis(mistral-nemo:12b):available → default_extract(mistral-nemo:12b):available
- **email_action_extraction_json** → selected `default_extract` (mistral-nemo:12b) · reason `selected_routed` · safety `metadata_only_advisory` · no-cloud True
  - chain: default_extract(mistral-nemo:12b):available
- **email_followup_raw_enrichment** → selected `default_extract` (mistral-nemo:12b) · reason `selected_routed` · safety `bounded_raw_input_redacted_output` · no-cloud True
  - chain: default_extract(mistral-nemo:12b):available
- **procore_digest_summary** → selected `default_extract` (mistral-nemo:12b) · reason `selected_routed` · safety `metadata_only_advisory` · no-cloud True
  - chain: default_extract(mistral-nemo:12b):available
- **relationship_scoring** → selected `review_filter` (qwen2.5:14b) · reason `selected_routed` · safety `metadata_only_advisory` · no-cloud True
  - chain: review_filter(qwen2.5:14b):available → default_extract(mistral-nemo:12b):available
- **short_operator_catchup** → selected `brief_synthesis` (mistral-nemo:12b) · reason `selected_routed` · safety `redacted_advisory` · no-cloud True
  - chain: brief_synthesis(mistral-nemo:12b):available → default_extract(mistral-nemo:12b):available
