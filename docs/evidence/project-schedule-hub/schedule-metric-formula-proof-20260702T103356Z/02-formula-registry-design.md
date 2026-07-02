# Formula registry design

Registry: `schedule_metric_formula_registry.py`

Version: `2026-07-02.schedule-metric-formula-proof.v1`

Each entry includes: `formula_supported`, `proof_supported`, `api_active`, `chart_active`, `reason_chart_inactive`, `zero_denominator_policy`, `weighting_policy_validated`.

Proof-only metrics (`chart_active: false`): `schedule_compression_index_internal`, `future_acceleration`, `critical_indices`.

Unsupported: `earned_value_spi`, `cost_weighted_percent_complete`, `resource_weighted_percent_complete`.
