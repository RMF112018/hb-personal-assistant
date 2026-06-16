# Tropical example

This folder documents how the Tropical World Nursery Senior Living Facility (`tropical`,
`23-435-01`, `2026-June`) run is wired into the subproject.

- `input_inventory.example.json` — the consolidated generator scripts (with source paths + SHA-256)
  and the authoritative crosswalk coverage facts.
- `command_examples.md` — copy-paste commands for validation and generation.

Source forecast packages live under the configured `default_data_root` (see
`config/projects/tropical.json`) and are **not** copied into the repo — only the generators, the
authoritative crosswalk, and config are tracked here. Generated outputs are written to new timestamped
package folders under the data root and are never committed.
