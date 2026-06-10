# Reference — Audit Findings Used by This Package

Private audit root:

`/tmp/hb-daily-brief-db-usefulness-audit-20260610-044631`

Audit DB:

`/tmp/hb-daily-brief-db-usefulness-audit-20260610-044631/prod-backup-20260610-044631.sqlite`

The audit used `sqlite3 .backup`, schema V45, and both integrity checks passed.

## Scorecard

| Metric | Value |
|---|---:|
| calendar_project_resolution_rate | 0.0 |
| calendar_near_term_event_count | 8 |
| calendar_unassigned_project_like_count | 8 |
| procore_open_signal_count | 5,866 |
| procore_due_soon_count | 0 |
| procore_recent_signal_count | 1,888 |
| procore_aggregate_sludge_count | 3,592 |
| followup_open_count | 0 |
| email_model_ready_thread_count | 0 |
| email_enrichment_pending_count | 0 |
| daily_brief_candidate_count | 0 |
| candidate_source_ref_coverage | 0.0 |
| project_key_coverage | 0.0 |
| actionability_verdict | partially_useful_but_blocked |

## Contradictions

- Procore open rows exist but daily-brief Procore section rows are zero.
- Calendar near-term rows exist but daily-brief calendar/meeting rows are zero.

## Top Findings

- Calendar has 8 near-term events; project resolution rate is 0.0%.
- 8 near-term calendar events look project-related but remain unassigned.
- Procore has 5,866 open signals, but only 0 due soon and 1,888 recent.
- 3,592 Procore open signals fall into aggregate-sludge groups.
- No daily brief action candidates exist for the target date.

## Remediation Targets

- Add project alias resolution before calendar-prep candidate persistence.
- Rank Procore by due/recent/high-critical/change-linked signals and suppress aggregate backlog groups.
- Fix daily-brief read-model projection so source rows actually appear in deterministic sections.
- Require candidate source refs before model-facing daily brief selection.

## Project Alias Starting Points

These are audit starting points, not authoritative mappings. The implementation must verify against repo/project truth.

| observed_token | observed_context | likely_project_key | confidence | recommended |
|---|---|---|---|---|
| Financial Forecast | [DUE TODAY] Project Financial Forecasts | __needs_review__ | low | classify internal/company or review |
| TWN | TWN Weekly LUNCH & Team Meeting | __needs_review__ | low | verify project truth |
| Wellington | Pre-Submission Bid Review - The Wellington Homes | the-wellington | medium | map if project truth supports |
| TWN, RFI, Submittal | TWN Weekly RFI/Submittal Review | __needs_review__ | low | verify project truth |
| TWN, OAC | TWN OAC | __needs_review__ | low | verify project truth |
| PTO | Andrew PTO | __needs_review__ | low | classify internal/time_off |
| Hilltop, Alton | FW: Alton Hilltop Bi-Weekly | hilltop | medium | map if project truth supports |
| Training | LMA Training: Group #2 - Session #5 Clarity & Recognition | __needs_review__ | low | classify internal/training |
