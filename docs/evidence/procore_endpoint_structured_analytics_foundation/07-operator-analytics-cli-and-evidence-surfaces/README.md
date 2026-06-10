# 07 Operator Analytics CLI And Evidence Surfaces

New CLI surfaces:

- `procore analytics contract`
- `procore analytics coverage`
- `procore analytics reprocess`
- `procore analytics structured-counts`
- `procore analytics ranking-diagnostics`
- `procore analytics no-raw-leak-scan`

All surfaces are local-only. `reprocess --apply` requires an explicit `--db`; dry-run writes nothing.
JSON outputs are stable and tests cover contract/reprocess behavior.
