# Phase 8A Findings

- Added a selected-baseline service to validate current and selected baseline schedule versions before persistence.
- Existing GET and PUT baseline route shapes were preserved.
- GET remains viewer-readable.
- PUT remains operator/admin-gated.
- Existing project_schedule_baseline_selections history behavior is preserved: a new active selection supersedes the previous active selection.
- No schema migration was added.
- No UDF normalization, import pipeline change, baseline override workflow, or frontend formula computation was added.
- Hub summary now reports selected-baseline readiness instead of treating every active selection as ready.
- Prior-update comparison remains separate from selected-baseline comparison.
- Schedule Compression Ratio is readiness-aware when requested and remains unavailable without a selected baseline.
