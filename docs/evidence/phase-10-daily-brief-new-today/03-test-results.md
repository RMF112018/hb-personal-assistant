# 03 — Test results (Phase 10 · 252 · New Today)

Toolchain: `.venv/bin/python3.12` (the real 3.12 toolchain; bare `.venv/bin/python` is an empty 3.14).

## New tests — `tests/test_phase_10_new_today.py` (24 passed)

Covers the reviewer's hard requirements:

- **Per-family business sentences (revision 7), exact / near-exact:** email contract-status request,
  Procore invoice (vendor/number/amount/period/status), RFI (number/title/status/cost-impact/ball-in-
  court), RFI response, change order, commitment, SharePoint file, calendar meeting.
- **Regression guard:** output never contains "…signal", "attendees / domains", the
  `Procore Financial / Project Signals` header, or count-only summaries.
- **Contract:** header `Today's Daily Brief`; subhead `Summary of the top items for 2026-06-12 and
  prep through 2026-06-19`; New Today is the first section; attention groups ordered; no raw project
  keys anywhere.
- **Detail-or-drop:** detail-missing Procore rows demote to diagnostics and never render as items.
- **Email usefulness gate:** substrate present + zero actionable ⇒ `email_degraded=True` + warning.
- **Refresh window:** deterministic fallback contract + a run-markers window from real sync runs.
- **Ollama overlay (mock):** polishes `why_it_matters`/`recommended_action` while the deterministic
  `summary_text` is unchanged; a leaky field withholds the whole layer; receipt is hash-only.
- **Deterministic fallback (no model):** still produces usable, raw-safe items.
- **Markdown ↔ HTML parity:** same business anchors in both; New Today precedes the collapsed
  diagnostics; both surfaces egress-clean.
- **Persistence:** guard columns zero after `--apply`; `--max-persist` fail-closes; `/tmp`-only apply
  guard; dry-run writes nothing; JSON proof raw-free.

## Regression suite (13 files, all passed, exit 0)

`test_phase_10_new_today`, `test_phase_10_daily_run`, `test_phase_10_daily_run_reliability`,
`test_phase_10_daily_brief_rendering`, `test_phase_10_daily_brief_user_facing_render`,
`test_phase_10_daily_brief_assembly`, `test_phase_10_daily_brief_correction`,
`test_phase_10_daily_brief_ranking_cli`, `test_phase_10_daily_brief_ranking_usefulness_gate`,
`test_daily_brief_html_render_agent`, `test_phase_10_candidate_lifecycle_daily_brief`,
`test_phase_10_daily_brief_source_ref_gate`, `test_phase_10_daily_brief_intelligence_convergence`.

The `render_daily_run_html` signature change (added `new_today`) and the `project_label` →
display-name change caused no regressions.

## Lint / type

- `ruff check` — all checks passed (new + edited src + tests).
- `ruff format` — applied.
- `mypy` — clean on the in-scope `construction.second_brain.*` new/edited modules
  (`new_today_digest`, `new_today_presentation`, `ollama_new_today`, `daily_run`, `daily_run_html`).
