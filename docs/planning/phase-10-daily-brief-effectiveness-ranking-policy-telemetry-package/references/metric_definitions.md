# Metric Definitions

All metrics are deterministic and observational. They are not causal unless the repo later adds true A/B assignment.

## Outcome Weights

Default outcome weights:

- accepted: `+1.0`
- closed/resolved after acceptance: `+1.0`
- reopened: `+0.2`
- snoozed: `+0.1`
- stale accepted: `-0.2`
- ignored after review window: `-0.4`
- rejected: `-0.8`
- suppressed: `-0.9`
- merged as duplicate/source: `-0.3` for clutter, `+0.2` for duplicate handling when cluster was advised

## accepted_rate

`accepted outcomes / exposed ranked items eligible for review window`

## rejected_rate

`rejected outcomes / exposed ranked items eligible for review window`

## snoozed_rate

`snoozed outcomes / exposed ranked items eligible for review window`

## ignored_rate

`exposed ranked items with no lifecycle movement after configured lag window / exposed ranked items eligible for review window`

Do not treat absent feedback as acceptance.

## stale_accepted_recurrence

`stale accepted items resurfaced in window / accepted items resurfaced in window`

## rank_outcome_score

For each evaluated item:

```text
rank_weight = 1 - ((rank_position - 1) / max(candidate_count - 1, 1))
item_score = outcome_weight * rank_weight
rank_outcome_score = normalized mean item_score to 0..1
```

Accepted items ranking higher improve the score. Rejected/ignored items ranking higher lower the score.

## source_family_usefulness_score

Weighted usefulness by candidate/source family:

```text
0.45 * accepted_rate
+ 0.20 * source_ref_coverage
+ 0.15 * closed_or_progressed_rate
- 0.10 * rejected_rate
- 0.10 * ignored_rate
```

Clamp to `0..1`.

## procore_noise_score

For Procore-derived candidates:

```text
noise = (rejected + ignored + suppressed + false_duplicate_proxy) / exposed_procore_candidates
rank_weighted_noise adds more penalty when noisy items appeared in top ranks
```

High score means more noise. It must recommend tuning/review, not suppression automation.

## model_advice_validity_rate

`valid usable model advice / model attempts`

Valid means schema-valid, safety-clean, references known candidates, and no lifecycle-excluded references.

## advisory_adoption_proxy

`positively acted items where model advice contributed / positively acted items with model advice available`

This is a proxy, not causation.

## model_degradation_rate

`ranking/model runs with degraded/withheld/fallback/timeout/invalid/unsafe status / total ranking/model runs`

## duplicate_precision_proxy

`duplicate/similarity-advised clusters later merged/suppressed as duplicate / reviewed duplicate/similarity-advised clusters`

Mark insufficient when reviewed cluster count is below threshold.

## source_ref_coverage

`surfaced actionable items with source_ref_count > 0 / surfaced actionable items`

Coverage below 1.0 should degrade/fail honestly according to existing source-ref gate expectations.

## brief_usefulness_score

Recommended deterministic blend:

```text
0.30 * accepted_rate
+ 0.20 * rank_outcome_score
+ 0.20 * source_ref_coverage
+ 0.10 * low_noise_component
+ 0.10 * low_model_degradation_component
+ 0.10 * follow_through_component
```

Include sample size and confidence note.

## deterministic_vs_model_delta

Observed difference between deterministic replay/equivalent baseline and model-assisted observed ranking:

```text
model_assisted_score - deterministic_baseline_score
```

Mark non-causal unless true A/B assignment exists.

## feedback_calibration_lift

Observed score difference between calibrated policy version and baseline/prior policy:

```text
calibrated_policy_score - baseline_policy_score
```

Mark insufficient when sample is too small or baseline is unavailable.
