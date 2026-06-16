# Tropical — command examples

All commands are run from the subproject root:

```bash
cd /Users/bobbyfetting/hb-personal-assistant/subrepos/construction-financial-review
```

## Validate the authoritative crosswalk (no install required)

```bash
PYTHONPATH=src python3 -m construction_financial_review.cli validate-crosswalk --project tropical
```

Expected: a JSON report with `"passed": true`, `crosswalk_row_count: 58`, full 127/42 coverage (when
the forecast context package is present at the configured data root), and all required mapping facts
true.

## Validate the crosswalk file directly (module form)

```bash
PYTHONPATH=src python3 -m construction_financial_review.mapping.validate_owner_sov_scope_crosswalk \
  config/crosswalks/tropical/owner_sov_scope_crosswalk_tropical_authoritative_20260614_final.jsonl \
  --context-package "/Users/bobbyfetting/Library/CloudStorage/SynologyDrive-BFmacSync/Work/NAS - HB/Projects/2023/TWN - NAS/30_Financials/Forecasts/Data/2026-June/forecast_context_package_tropical_20260614_084510"
```

## Run the generators (Tropical-only; write to new timestamped folders)

```bash
scripts/run_tropical_context.sh
scripts/run_tropical_analysis.sh
scripts/run_tropical_mapping_workpaper.sh
scripts/run_tropical_crosswalk_v2.sh
```

A non-tropical project exits non-zero with a clear "not yet parameterized" message:

```bash
PYTHONPATH=src python3 -m construction_financial_review.cli run-context --project someproject  # -> exit 2
```

## Tests

```bash
# With the repo dev venv (pytest installed):
/Users/bobbyfetting/hb-personal-assistant/.venv/bin/python -m pytest
# Or, after `pip install -e ".[dev]"` in a local venv:
pytest
```
