# Phase 14 — Schedule Import Observability + CPM Trust Layer

**Branch:** `feature/schedule-import-observability-cpm-trust-phase14-20260701T163525Z`  
**Base:** `d86d59de`  
**Verdict:** Ready for operator review (no push/PR without approval)

## Amendments satisfied

1. **analytics_trust_status gate rules** — Normative rules in `project_schedule_analytics_trust_service.py`; covered by `tests/test_project_schedule_analytics_trust.py`.
2. **Out-of-sequence progress** — Surfaced only as `capability_limitations`, not schedule-quality defects.
3. **CPM failure redaction** — Raw exception text removed from preview/commit/status/hub/controls/export payloads; DB observability retains raw `failure_message`.
4. **HTML-in-ZIP** — Proven ignored via `test_zip_html_companion_is_ignored_not_parsed`; no HTML parser added.
5. **Comparison basis propagation** — Drivers API, hub drilldowns, driver evidence, controls, workbench/export links unified on `controlsComparisonBasis`.
6. **Named-baseline regression** — Suite passed (workbench, export, hub API); frontend `ProjectSchedulePage` tests updated and passing.

## Validation commands

```bash
export PYTHONPATH="$PWD/src:$PWD/subrepos/construction-financial-review/src"
source /Users/bobbyfetting/hb-personal-assistant/.venv/bin/activate

python -m pytest \
  tests/test_project_schedule_analytics_trust.py \
  tests/test_schedule_cpm_import_observability.py \
  tests/test_project_schedule_import_pipeline.py \
  tests/test_project_schedule_named_baseline_workbench.py \
  tests/test_project_schedule_named_baseline_export.py \
  tests/test_project_schedule_hub_api.py \
  -q

cd frontend && npm ci && npm test -- --run ProjectSchedulePage.test.tsx
```

## Key surfaces

| Surface | analytics_trust | CPM redaction |
|---------|-----------------|---------------|
| Import preview | yes | n/a |
| Import commit / status | yes | `failure_message_redacted` |
| Hub summary | yes | via ledger |
| Controls | yes | via ledger |
| Export memo | trust section | no raw failures |
