# 04 — Deterministic Daily-Brief Render (no model)

Rendered with `second-brain daily-brief render --db <tmp copy> --date 2026-06-12` after a
deterministic `rank-candidates --no-client` run (model layer withheld; deterministic ranking
authoritative). This is the exact user-facing Markdown — it passes the presentation output fence
(no internal ids, sentinels, hash labels, `next:review`, table/column names, or raw content).

```markdown
# Daily Brief — 2026-06-12

_Advisory only. A deterministic, source-linked action plan from the local-agent family (email/follow-up, Procore, calendar). No raw source content._

## Top Priorities
- alton-hilltop-pbg — RFI cost-impact signal. Confirm pricing exposure and response owner.
- tropical — payment-due invoice signal. Review payment status and confirm next payment action. (×4)

## Calendar Prep
- Project meeting — alton-hilltop-pbg — 7 attendees / 2 domains / in person / TBD. Review the meeting and prepare notes.
- Project meeting — alton-hilltop-pbg — 10 attendees / 5 domains / online. Review the meeting and prepare notes.
- Project meeting — alton-hilltop-pbg — 26 attendees / 10 domains / online. Review the meeting and prepare notes. (×2)
- Project meeting — alton-hilltop-pbg — 11 attendees / 3 domains / online. Review the meeting and prepare notes. (×2)
- Project meeting — alton-hilltop-pbg — 5 attendees / 2 domains / in person / TBD. Review the meeting and prepare notes.
- Project meeting — alton-hilltop-pbg — 10 attendees / 3 domains / online. Review the meeting and prepare notes.
- Project meeting — pga-modern-garage — 19 attendees / 8 domains / online. Review the meeting and prepare notes. (×2)
- Project meeting — pga-modern-garage — 6 attendees / 1 domains / online. Review the meeting and prepare notes. (×2)
- Project meeting — pga-modern-garage — 3 attendees / 1 domains / online. Review the meeting and prepare notes.
- Project meeting — tropical — 9 attendees / 1 domains / online. Review the meeting and prepare notes. (×4)
- Project meeting — tropical — 24 attendees / 9 domains / online. Review the meeting and prepare notes.
- Project meeting — tropical — 1 attendees / 1 domains / in person / TBD. Review the meeting and prepare notes. (×2)
- +16 more meetings (open the full review queue to see them all).

## Procore Financial / Project Signals
- tropical — 18 payment-due invoice signals, 10 approved-not-paid invoice signals, 6 negative budget variance signals, 5 unpaid commitment change-order signals. Review payment status and confirm next payment action.
- alton-hilltop-pbg — 1 RFI cost-impact signal. Confirm pricing exposure and response owner.

## Email / Follow-up
- Email follow-up unavailable — 281 email thread summaries exist, but none are eligible for follow-up watch. Review the email follow-up projection/watch eligibility inputs.

## Data Gaps / Degraded
- Advisory model layer unavailable; deterministic ranking is authoritative for this brief. No action needed — the priorities above are complete.
```

Key properties:
- Consumes the V51 assembly overlay (Top Priorities first), not the prior flat family dump.
- Procore aggregated by project + signal type; calendar safe-labelled; email/follow-up data-gap card.
- Deterministic and model-independent (`--no-client`); identical across repeated runs.
