# 05 — Source vs Computed Field Map

This package distinguishes **imported/source** schedule fields from **application-computed CPM**
fields. The core provenance guarantee: **source critical / driving-path / float fields are NOT
used to produce application-computed CPM evidence**. Computed CPM responses return app-owned
fields only, drawn from the persisted CPM runs. Source-export evidence is kept **separate**.

## Provenance table

| Concept | Source (imported) field | Application-computed field | Used for app-computed CPM? |
| --- | --- | --- | --- |
| Early start/finish | imported early dates (XER) | computed early start/finish (forward pass) | computed only |
| Late start/finish | imported late dates (XER) | computed late start/finish (backward pass) | computed only |
| Total / free float | imported/source float | computed total/free float (float run) | computed only |
| Critical flag | source critical flag | `is_critical` (criticality run) | **source NOT used** |
| Driving path | source driving-path flag | longest-path membership (`schedule_cpm_path_activities`) | **source NOT used** |
| Criticality class | (n/a in source) | computed criticality class (criticality run) | computed only |
| DCMA critical-path metric | (would be source-derived) | `available_app_cpm_recalculated` measured status | computed only |

## Explicit guarantees (evidence-backed)

- **`source_critical_flags_used: false`** — present in both
  `artifacts/dcma-computed-cpm-sample.json` (`result.evidence.source_critical_flags_used`) and
  `artifacts/api-cpm-summary-sample.json` (`dcma_critical_path.source_critical_flags_used`).
- **`source_export_evidence: "separate"`** / **`evidence_class: "application_computed_cpm"`** —
  present in the API summary and DCMA sample, marking that source-export evidence is a distinct
  track and not mixed into application-computed CPM.
- The CPM read service exposes only an **app-owned `_ACTIVITY_WHITELIST`**
  (`schedule_cpm_read_service.py:40`); it does not surface raw source critical/driving/float
  fields in CPM responses.
- The pure DCMA evaluator (`schedule_cpm_dcma_integration.py`) performs **no SQL and no
  source-field reads** — it decides measurability purely from the application-computed CPM run
  outputs.

## Source-export evidence stays separate

Any evidence derived from the imported source export (e.g. source critical flags as exported by
the authoring tool) is intentionally **not** combined with application-computed CPM evidence in
this package. The two are evaluated on separate tracks so that "computed CPM" claims rest only
on the engine's own forward/backward/float/longest-path/criticality computation.
