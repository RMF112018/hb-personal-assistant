# 26 — Known Limitations

Real limitations remaining after this first slice (none block merge of the slice itself):

1. **Email → follow-up extraction is readiness-only.** This slice surfaces the email/follow-up
   data gap honestly (a card: "email raw content available but follow-up projection not yet
   populated") and gates on it, but does NOT build the semantic email follow-up extraction agent.
   `task_candidates` / `commitment_candidates` / `follow_up_watch_items` stay 0 until that
   extraction is built (explicitly out of scope per SCOPE_LOCK). The pre-existing model-dependent
   extraction test (`test_phase_10_email_task_extraction.py`) remains environment-gated.

2. **Procore due-date coverage is zero.** Open Procore signals carry no `due_at_utc` in the current
   data, so "why-today" ranking uses recent / source-change / financial / importance dimensions
   only. Reported as a data-quality gap (`due_date_coverage_low`), not fabricated. A future slice
   could extract due dates from raw payloads.

3. **Project identity is a deterministic first pass.** The backfill populates
   `construction_project_identity` (0 → 6 on the copy) from local source truth and flags conflicts
   as `review_required`; it is not wired as a live daily-run stage (calendar project resolution
   already reaches 100% in-window via the alias resolver). `construction_project_source_matches`
   stayed 0 in the copy (no deterministic source links present in this data) — honest, not an error.

4. **Production-DB byte-level unchanged proof is N/A during the run.** An operator-started
   `graph mail index --no-dry-run --include-raw-content` backfill (PID 21473) was concurrently
   writing the PLAIN production DB throughout validation. Per operator decision, validation ran
   against frozen `/tmp` copies and the production-safety guarantee is "no write path of this slice
   touched production" rather than a literal before==after hash (see `23`). Production grew ~0.8 GB
   during the session purely from that backfill.

5. **Structured email projection lags raw ingestion.** Because the backfill is actively adding raw
   email rows, the structured projection count trails the raw count at any instant; the projection
   stage is idempotent and re-projects on each apply run, so a daily apply converges it.

6. **Calendar candidate volume is window-bounded.** The integrated run persisted 6 calendar
   candidates (the weekday-policy window), versus ~25–50 under a wider manual lookahead. This is the
   intended daily-window behavior, not a defect.
