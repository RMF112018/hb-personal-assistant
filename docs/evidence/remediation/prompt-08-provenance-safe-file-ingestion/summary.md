# Prompt 08 Remediation Evidence: Provenance-Safe File Ingestion

## Objective

Separate synthetic demo paths from real file ingest paths and fail closed when provenance is invalid or incomplete.

## Starting Checks

- `git status --short`:
  - `?? .tmp-app-support-remediation/`
  - `?? docs/plans/my-pa-phase-0/gap-closure/`
- `git branch --show-current`: `main`
- `git rev-parse HEAD`: `47dc343b03dd4d88890f559df59e657321f2d25b`
- `git log --oneline -5`: captured in `04-git-log.txt`
- `python --version`: `command not found` (exit `127`)

## Implementation Results

- Added explicit CLI split:
  - `hb-assistant files sample --json` (synthetic only)
  - `hb-assistant files ingest --dry-run --json` (real persisted candidates only)
- Removed synthetic fallback from `files ingest`.
- Added store helper for real provenance-backed ingest candidates.
- Enforced fail-closed service guards:
  - missing/invalid provenance (`source_record_id`)
  - incomplete Graph metadata (`id`, `name`, `size`)
  - manual approval gate respected
  - source-link failure surfaces as ingest error
- Removed implicit `source_record_id=0` behavior in real persistence/update paths.

## Validation Commands

- `python -m pytest tests/test_file_ingestion.py tests/test_files*.py` -> exit `127` (`python` unavailable)
- `.venv/bin/python -m pytest tests/test_file_ingestion.py tests/test_files*.py` -> exit `0` (`14 passed`)
- `HB_PA_CONFIG=/private/tmp/hb-pa-remediation-p08.yml .venv/bin/hb-assistant files sample --json` -> exit `0`
- `HB_PA_CONFIG=/private/tmp/hb-pa-remediation-p08.yml .venv/bin/hb-assistant files ingest --dry-run --json` -> exit `1` with truthful `no_provenance_candidates`

## Supersession and Isolation Notes

- Prior closeout assumptions remain superseded pending remediation acceptance.
- Unrelated untracked paths were preserved and untouched:
  - `.tmp-app-support-remediation/`
  - `docs/plans/my-pa-phase-0/gap-closure/`
