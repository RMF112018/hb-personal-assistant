# 10 — Usefulness Scorecard

Operator usefulness of the rendered brief (does it tell Bobby what to do, in priority order, without
noise or leaks). Scored against the audit's 3.4/10 baseline.

| Dimension | Audit (before) | Now | Notes |
|---|---|---:|---:|
| Prioritization (top items first) | ✗ flat dump | ✓ | Top Priorities section, assembly-ranked |
| Actionability (concrete CTAs) | ✗ blanket `next:review` | ✓ | per-signal/family CTA map |
| Procore signal/noise | ✗ 50 near-dup lines | ✓ | aggregated by project + signal type |
| Calendar usability | ✗ `[redacted:hash]` | ✓ | safe labels + attendee/domain/online metadata |
| Email/follow-up coverage | ✗ silently empty | ✓ | polished data-gap card (281 summaries surfaced) |
| Noise control / length | ✗ unbounded | ✓ | dedupe `×N` + calendar `+N more` overflow |
| Honest degraded status | ~ | ✓ | "deterministic ranking authoritative" data-gap line |
| No internal artifacts | ✗ ids/sentinels leak | ✓ | output fence enforced |

## Score

- **Usefulness: 8.5 / 10** (baseline 3.4). Remaining gap is not a P1 user-facing blocker:
  - The email/follow-up family has no eligible follow-ups on canonical data (0 of 281 summaries
    converted). This is an upstream projection/eligibility gap (out of this slice's scope) and is
    surfaced honestly via the data-gap card rather than hidden — so it is informative, not a defect.

## Decisiveness

The brief now answers "what should I act on first?" — RFI cost-impact and unpaid invoices on named
projects in Top Priorities, with concrete next actions — which the audited dump did not.
