# 13 — Usefulness Scorecard

| Metric | Result | Gate |
|---|---:|---|
| Structured email rows available | 405 msg / 223 thread | nonzero PASS |
| Follow-up candidates generated (owner-configured) | 4 | per fixtures PASS |
| Daily-brief candidates persisted | 4 | idempotent PASS |
| Source-ref coverage | 1.0 | 100% PASS |
| Project-key coverage | 0.5 (review_required=2) | reported PASS |
| Invented project keys | 0 | must be 0 PASS |
| Data-gap preserved when none / replaced when present | yes / yes | required PASS |
| Idempotency replay | True | no duplicates PASS |
| Guard columns | all 0 | zero PASS |
| No-raw-leak scan | 0 findings | clean PASS |
| Production DB mutation | none (sha256 identical) | zero PASS |
| External writeback | none | zero PASS |

Honest note: subject-only metadata yields few follow-ups on a real snapshot (mostly time-sensitive);
body-derived families are a deliberate audited future pass.
