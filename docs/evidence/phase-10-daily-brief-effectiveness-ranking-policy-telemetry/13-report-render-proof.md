# Daily Brief Effectiveness — 2026-06-01 to 2026-06-30

_Status:_ ok

_Data sufficiency:_ sufficient

_Confidence note:_ observational_only_not_causal

_Ignored lag window:_ 72h

## Summary

- Brief count: 1
- Candidate count: 5
- Outcome count: 5
- Source-ref coverage: 1.0
- Brief usefulness score: 0.3865
- Rank-outcome score: 0.5325

## Outcome Distribution

- Accepted: 1
- Rejected: 2
- Snoozed: 1
- Ignored: 1
- Merged: 0
- Suppressed: 0
- Closed: 0
- Reopened: 0
- Stale (no action): 0

## Ranking Policy

- Policy version: rank-policy-v1
- Deterministic baseline rank-outcome: 0.51
- Model-assisted rank-outcome: 0.51
- Deterministic-vs-model delta: 0.0 (observational, non-causal)

## Source-Ref Coverage

- Coverage: 1.0 (1.0 = every surfaced actionable item is source-linked)

## Procore Noise

- Exposed Procore candidates: 1
- Noise score: 1.0

## Model Profile Reliability

- profile=default_extract attempts=3 degradation_rate=0.3333 fallback=1 status=ok

## Duplicate / Similarity Proxy

- Reviewed clusters: 0
- Duplicate precision proxy: —
- Insufficient sample: True

## Safe Next Tuning Actions

1. review_procore_prioritization: noise_score=1.0 (high clutter signal)
2. review_model_reliability: model_degradation_rate=1.0 (deterministic fallback dominated)

## Guardrails

- Observational only: true
- No lifecycle mutation: true
- No source-ref mutation: true
- No external writeback: true
- Raw-free report: true
