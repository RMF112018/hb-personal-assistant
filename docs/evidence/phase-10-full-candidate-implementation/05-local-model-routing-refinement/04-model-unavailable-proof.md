# Model-unavailable proof (fail-closed, deterministic fallback)

## Daemon unreachable → every task family fails closed (never cloud)
- families: 7; blocked: 7; available: 0
- all `no_cloud`: True
- all have a `fail_closed_reason`: True

## Primary model missing → deterministic local fallback (still never cloud)
- `relationship_scoring` with only `mistral-nemo:12b` present: available=True, reason_code=`selected_fallback`, fallback_from=`review_filter`, fallback_reason=`model_missing`, no_cloud=True
