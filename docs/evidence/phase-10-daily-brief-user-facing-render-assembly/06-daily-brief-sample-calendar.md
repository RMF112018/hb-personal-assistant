# 06 — Calendar Prep Section (safe labels)

`render --section calendar`. Sentinel project keys are mapped to actionable safe labels
(`__needs_review__` → "Calendar item needing project review", `__internal_time_off__` →
"Internal calendar block", real key → "Project meeting — <project>"). No `[redacted:<hash>]`
labels, raw subjects, attendee names, emails, or URLs. Metadata (attendee/domain counts,
online/in-person) comes from the candidate's pre-redacted reason field. The section is capped with
an explicit "+N more meetings" overflow line (no silent truncation).

```markdown
# Daily Brief — 2026-06-12

_Advisory only. A deterministic, source-linked action plan from the local-agent family (email/follow-up, Procore, calendar). No raw source content._

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

## Data Gaps / Degraded
- Advisory model layer unavailable; deterministic ranking is authoritative for this brief. No action needed — the priorities above are complete.
```
