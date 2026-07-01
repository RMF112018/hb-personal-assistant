# Phase 18A — Named-Baseline Green Gate

Evidence stamp: `20260701T210726Z`

## Artifacts

| File | Description |
|------|-------------|
| `00-repo-state.txt` | Branch, HEAD, status |
| `01-baseline-failure-reproduction.txt` | Pre-fix failure output (2 failed) |
| `02-repo-truth-audit.md` | Root-cause analysis |
| `03-test-results.txt` | Targeted + regression + acceptance suites (all green) |
| `04-fix-summary.md` | Service + test changes |
| `05-redaction-regression-proof.txt` | `find_redaction_leaks` on named controls payload |
| `06-known-limitations.md` | Residual limits |

## Reproduce pre-fix failures

```bash
git checkout ef00fc73
pytest tests/test_project_schedule_named_baseline_comparison_accuracy.py::test_prior_update_disposition_does_not_join_named_workbench \
  tests/test_project_schedule_multi_baseline_controls.py::test_controls_named_includes_workbench_links -q
```

## Validate fix

```bash
pytest tests/test_project_schedule_named_baseline_comparison_accuracy.py \
  tests/test_project_schedule_multi_baseline_controls.py \
  tests/test_project_schedule_named_baseline_workbench.py -q
```
