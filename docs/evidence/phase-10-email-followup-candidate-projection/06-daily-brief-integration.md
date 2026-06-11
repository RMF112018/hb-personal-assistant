# 06 — Daily Brief Integration

`email_followup_projection` is a generation stage inserted immediately after
`email_calendar_projection` in `pipeline.py` (STAGE_ORDER + generation set + builders), reusing the
existing per-stage cap / idempotency / receipt / brief_freshness machinery.

- Stage ordering proven by `test_pipeline_runs_email_followup_stage_and_flips_data_gap`.
- Data-gap card: data_gap -> populated once candidates persist; preserved when none are produced
  (readiness counts include task/commitment candidates).
- Receipt is raw-free: counts, family distribution, project coverage, review count, raw-access count
  (0), reason codes. Real-data sections landed: {"follow_up": 4} (executive sections only).
