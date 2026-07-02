# API activation design

## Routes

- `GET /api/projects/{project_key}/schedule/metric-proof` — primary proof surface
- `GET /api/projects/{project_key}/schedule/metrics/{metric_key}/trend` — existing chart path (unchanged)

## Activation cross-check

`build_activation_proof()` emits a per-metric `activation_matrix` (registry ↔ trend API ↔ metric-proof API ↔ frontend chart list). `activation_cross_check()` returns anomalies only. Unsupported weighting variants use `active_as_unsupported_metric`.
