# Backend test correction — Phase 13D

## Original mainline run (`02-backend-test-results.txt`)

**Result:** 97 passed, **2 failed**, 1 skipped

**Failures:**
- `test_project_schedule_populated_comparison_actions_and_no_mutation`
- `test_project_schedule_large_fixture_performance_under_two_seconds`

## Diagnosis (P3 test drift)

`_assert_default_pm_fields_have_no_raw_identifiers` rejected any JSON substring containing `schedule_version_key`. Phase 13A+ intentionally exposes provenance fields such as `comparison_schedule_version_key` in PM comparison context. The bare key was never present; the substring check was a false positive.

## Correction

Updated [`tests/test_project_schedule_hub_api.py`](../../../../tests/test_project_schedule_hub_api.py):

- Replaced substring scan with path-aware tree walk
- **Forbidden (exact key names only):** `schedule_version_key`, `schedule_identity_key`, `computed_cpm_health`, `identity_safe`, `source_export_proxy`
- **Allowed provenance keys:** `comparison_schedule_version_key`, `current_schedule_version_key`, `baseline_schedule_version_key`, `selected_baseline_schedule_version_key`, `previous_version_key`
- Raw version token pattern still enforced on other PM-facing string values

No API payload changes.

## Post-correction runs

| Command | Result |
|---------|--------|
| `pytest tests/test_project_schedule_hub_api.py -q` | **23 passed** |
| Focused named-baseline + hub suite (`02b-backend-test-results-post-correction.txt`) | **90 passed, 1 skipped** |

## Follow-up

Test-only change on verification branch — prepare small PR to `main` unless operator keeps local-only.
