# Evidence — Schedule XER Import UI (PR #93)

**Date stamp:** 20260622T163500Z

## What changed

- Frontend `ScheduleImportsPage` file input now accepts `.xer` alongside `.xml`, `.pmxml`, `.csv`.
- Upload label, subtitle, and parse/format error copy explicitly include Primavera XER.
- Backend XER path was already implemented (V67); added API tests confirming preview/commit/quality.

## Acceptance criteria

- UI allows selecting `.xer`
- API preview returns `source_format = primavera_xer` for `minimal.xer`
- Commit persists driving-path and explicit float fields
- Quality metric `dcma_critical_path_test.status = measured_from_xer_driving_path`
- XML/PMXML/MSP/CSV import paths unchanged

## Proof files

- `frontend_upload_control.txt` — accept attribute + copy
- `xer_api_preview.json` — preview response for `minimal.xer`
- `xer_api_commit.json` — commit response + activity count
- `xer_quality_proof.json` — `dcma_critical_path_test` metric snippet
- `backend_tests.txt` — pytest output
- `frontend_proof.txt` — vitest + `npm run build`