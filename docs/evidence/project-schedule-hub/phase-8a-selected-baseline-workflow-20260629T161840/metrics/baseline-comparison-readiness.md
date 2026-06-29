# Baseline Comparison Readiness

Phase 8A keeps prior-update comparison and selected-baseline comparison separate.

- Prior-update metrics continue to use the existing prior-update comparison context and canonical TWNU18 to TWNU19 values.
- Selected-baseline state is exposed under baseline-specific payload fields only.
- Schedule Compression Ratio is not computed in the frontend.
- Schedule Compression Ratio remains blocked with metric_not_trend_ready when no selected baseline exists.
- When a selected baseline exists but matching or duration facts are incomplete, the backend returns available false, recompute_required true, and readiness blockers.
- When matched unfinished activities and duration fields exist, the backend returns a selected-baseline payload with compression_ratio and comparison_basis selected_baseline.

Phase 8A does not enqueue or trigger CPM, import, or diff recomputation.
