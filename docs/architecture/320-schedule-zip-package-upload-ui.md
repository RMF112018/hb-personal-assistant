# ADR 320: Schedule ZIP Package Upload — UI/API Contract Alignment

## Status

Accepted — implemented on top of the V75 import-health foundation (ADR-less #151).

## Context

The schedule-import backend (`schedule_import_service.py`, added in #151) fully supports, validates,
and tests `.zip` package upload: it branches on `.zip` into `_read_zip_schedule_files`, enforces
path-traversal / nested-archive / decompressed-size / file-count guards, parses each member, separates
current vs. baseline projects, and persists V75 package metadata. The route `POST
/api/schedules/import-preview` already accepts the raw upload and returns the package fields
(`package_mode`, `files`, `current_project_candidates`, `baseline_project_candidates`, `capabilities`,
`warnings`). It was operationally proven against `TWN.zip`, `Caretta.zip`, and `BlueLake.zip`.

The React upload page (`frontend/src/pages/ScheduleImportsPage.tsx`), built earlier, never exposed
this: its `accept` list excluded `.zip` and it rendered only single-file preview fields. The `.zip`
extension was never present in the UI — never added, never removed — so this was an **incomplete
implementation**, not a regression. Two adjacent defects also surfaced: macOS archive metadata
(`__MACOSX/`, AppleDouble `._*`) inside real ZIPs was parsed as schedule files and failed noisily, and
packages carrying multiple non-equivalent current schedules were silently auto-resolved.

## Decision

- **Expose the existing backend in the UI** (no reimplementation): add `.zip` to `accept`, render the
  package manifest (files discovered, selected current + "XER preferred over XML" reason, baseline /
  supporting candidates, ignored files & warnings), and surface package/ZIP error codes with curated
  copy.
- **Multi-file semantics (v1):** keep the backend's deterministic auto-selection (XER preferred) with a
  transparent manifest. `.xer` + `.xml` of the same schedule snapshot are equivalent and auto-resolve;
  multiple **non-equivalent** current schedules (distinct calendar `YYYY-MM-DD` data dates) are
  **blocked** with `schedule_package_multiple_current_candidates` (HTTP 409, candidate list in payload).
  Equivalence is keyed on the data-date prefix only, because cross-format `project_id` strings differ
  (e.g. XER `1070` vs XML `CARETTAU27`).
- **Member filtering:** skip `__MACOSX/` sidecars, AppleDouble `._*`, dotfiles, and directory entries in
  `_read_zip_schedule_files` before extension dispatch.

## Guardrails

- Backend ZIP safety guards from #151 are unchanged (`schedule_zip_invalid`,
  `schedule_zip_too_many_files`, `schedule_zip_unsafe_path`, `schedule_zip_nested_archive`,
  `schedule_zip_too_large`, `schedule_zip_read_failed`, `schedule_package_no_valid_files`).
- No schema, migrator, or count change. The new ambiguity error reuses the existing structured-error
  mapping (`_raise_schedule_import_error`).
- Tests: backend `__MACOSX`-ignored and ambiguity-block cases
  (`tests/test_schedule_import_health_foundation.py`); frontend package-manifest render, ambiguity
  block, and curated-copy cases (`ScheduleImportsPage.test.tsx`). Validated against the real `TWN`,
  `Caretta`, `BlueLake` ZIPs (preview 200 / `zip_package`, no AppleDouble noise).

## Deferred (Phase 2)

- Explicit operator selection UI for ambiguous multi-current packages (today they are blocked).
- Richer non-data-date ambiguity detection (e.g. same date, materially different project identity).
