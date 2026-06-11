# Reference — Updated Audit Baseline

The raw projection follow-up audit concluded:

- The original issue is no longer primarily missing raw data.
- Raw email/calendar and Procore endpoint payload availability materially improved.
- V49 email/calendar structured projection architecture exists in code/schema.
- The attached DB had V49 schema but structured email/calendar projection tables were empty.
- Daily brief candidates and candidate source refs were still empty.
- Project identity/promotion tables were still empty.
- Procore endpoint projections are rich enough for analysis, but broad action signals remain noisy unless ranked/suppressed.
- Calendar raw data exists but project-key coverage remains weak.
- Email raw data exists but follow-up/task/commitment layers remain empty.
- The next implementation slice should focus on projection activation, source-linked candidate persistence, project identity promotion, and hard usefulness/source-ref gates.

Baseline counts from the audit are in the README. Recompute them from the current DB copy before implementation because repo/DB state may have advanced.
