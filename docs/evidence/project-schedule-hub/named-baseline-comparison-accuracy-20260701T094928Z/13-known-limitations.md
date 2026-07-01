# Known Limitations (Phase 13A)

## Named baseline export memo (`narrative_qa_failed`)

`GET /api/projects/tropical/schedule/export?comparison_basis=current_contract_baseline` returns **422** with `detail: narrative_qa_failed` on the Tropical real DB. Prior-update export succeeds (200). Drilldown and controls surfaces are named-aware; export QA gate needs a follow-up slice to accept named-baseline comparison summaries.

Captured in `api-export-markdown-current_contract_baseline.json`.

## Legacy `baseline` controls unavailable on Tropical

`comparison_basis=baseline` controls return `available: false` (no active legacy baseline selection for current as-of). Named slots are the supported baseline path on Tropical.

## Workbench GET vs POST

Named workbench **GET** returns preview scope with zero items until operator **POST** sync materializes cues. Evidence uses POST sync for cue-basis proof (`api-workbench-sync-*.json`) without additional PATCH mutations during 13A capture.

## Performance on real DB

Tropical controls/drilldown requests can exceed 15s per basis on the operator laptop; browser capture uses 180s load waits. This is observability-only, not a correctness defect.

## Screenshot disposition state

Shot `05-controls-disposition-item` captures the named workbench after Phase 13 sync materialization (open/watching items may appear). A dedicated controls-card disposition badge depends on top_controls linking to persisted named items — verify against `api-named-workbench-disposition-sample.json`.
