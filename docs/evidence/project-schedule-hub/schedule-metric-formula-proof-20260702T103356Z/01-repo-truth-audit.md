# Schedule metric formula repo-truth audit

## Summary

Most dashboard metrics are implemented in `project_schedule_trend_aggregation_service.py` and UDF normalization. This phase adds deterministic proof layer without aggressive trend refactor.

## Proof dimensions

| Metric | formula_exists | active | arithmetically_accurate | weighting_policy_validated | proof_readiness |
|--------|----------------|--------|-------------------------|----------------------------|-----------------|
| Planned vs Actual | yes | yes (trend + proof) | yes (fixture) | n/a | pass_fixture |
| SPI / schedule_performance_ratio | yes | yes | yes (internal SPI) | n/a | pass_fixture |
| Schedule Changes | yes | yes | partial | n/a | pass_fixture; near_critical needs prior CPM |
| Schedule Delay | yes | yes | partial | n/a | pass_fixture prior_update |
| Delay Analysis | yes | yes | conditional | n/a | not_computable_missing_udf on minimal XER |
| Window Start | yes | yes | conditional | n/a | not_computable_missing_udf on minimal XER |
| Should Have Finished | yes | yes | conditional | n/a | pass_fixture or not_computable |
| Critical Issues | yes | yes | partial | false | pass_with_policy_limitations |
| Compression analog | yes | proof API | partial | false | pass_with_policy_limitations |
| Health Index | yes | yes | yes (composite) | false | pass_with_policy_limitations |
| Feasibility | yes | yes | partial | false | pass_with_policy_limitations |
| Future Acceleration | yes | proof API | partial | n/a | pass_fixture or not_computable |
| Critical Indices | yes | proof API | partial | false | pass_with_policy_limitations |
| EV SPI | no | no | n/a | n/a | unsupported |
| Cost/resource % complete | no | no | n/a | n/a | unsupported |

Policy note: composite scores are computationally provable; weights require PM/business validation.
