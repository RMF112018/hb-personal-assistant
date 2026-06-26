# Package Manifest Examples

## ZIP With XML Baseline

Preview now returns package fields while preserving existing preview fields:

- `package_id`
- `package_mode`
- `files`
- `current_project_candidates`
- `baseline_project_candidates`
- `capabilities`
- `warnings`

Unsupported files in ZIP packages are ignored with warnings when at least one schedule-bearing file parses.

## XER + XML Precedence

When both XER and XML contain current schedule evidence, the manifest records field-family source precedence:

- current float/source-critical/source-options: XER
- baseline entities: XML
- canonical current schedule rows: persisted once
