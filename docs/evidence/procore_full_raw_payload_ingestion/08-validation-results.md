# 08 — Validation results

## pytest

- `tests/test_procore_full_raw_payload_ingestion.py` — **11 passed** (new).
- `tests/test_procore_structured_analytics_foundation.py` — **18 passed** (unchanged).
- live-sync chains (`verified_chain`, `phase05_chain`, `n1_children`) — **45 passed**.
- broad sweep `-k "procore or structured_analytics or backfill"` — **all passed, 1 skipped**.

Pre-existing, unrelated: `test_launcher_scheduler.py::test_production_default_no_hb_procore_live`
fails identically on clean `main` (an `HB_PROCORE_LIVE` env-leak in that test); not a
regression from this change.

## ruff

`ruff check` on the touched src + test files — **All checks passed!**

## mypy

`mypy src/hb_assistant/procore/structured_analytics.py` — **Success: no issues found**.

## DB-copy validation (production untouched)

Production DB resolved via `PathPolicy().get_db_path()`:
`…/HB Personal Assistant/db/hb-personal-assistant.sqlite`.

- prod sha256 BEFORE: `fd7c8e9aec618ed5de4d1edf734237811d5dfe07e9ac933eb0825a0041146cb6`
- prod sha256 AFTER all validation: **identical** (unchanged).
- All writes performed on a `/tmp` copy via `sqlite3.Connection.backup`; copy deleted after.

On the copy:

- migrator applied → head `46` (additive no-op).
- pre-existing state: `procore_endpoint_raw_payloads` = 30,059 rows, all
  `redacted_legacy_projection` / `raw_procore_payload_persisted=0`.
- full fixture write (`fixture_full_payload`): 1 raw row `raw_procore_payload_persisted=1`,
  structured `amount=12345.67` populated, injected `access_token` value absent from
  `payload_json`.
- `scripts/procore_full_raw_probe.py` confirmed the source-quality distribution and
  printed field names + hash prefixes only (no bodies).

## Artifacts

No forbidden artifacts staged (`*.sqlite` / `*.db` / `*.pyc` / `.env` — `__pycache__` is
gitignored). `/tmp` validation copy removed.
