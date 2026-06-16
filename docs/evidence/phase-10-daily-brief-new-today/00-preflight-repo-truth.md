# 00 — Preflight repo-truth (Phase 10 · 252 · New Today)

## Branch / HEAD at start

- Branch: `feature/phase-10-ollama-candidate-ranking-brief-assembly`
- HEAD: `fb324eaa fix(second-brain): sanitize daily-run browser brief output (251 v2)`
- Schema version before this slice: `LATEST_SCHEMA_VERSION = 53`; the production DB observed at V52.

## Problem (why this slice exists)

The daily brief opened with abstract, candidate-derived content — `Top Priorities`, `Calendar Prep`,
`Procore Financial / Project Signals`, `Email / Follow-up: None`, plus status banners — i.e. signal
families, counts, and generic CTAs instead of actual business events. It told Bobby "22 payment-due
invoice signals" rather than "Coastal Pipeline submitted Invoice #1842 for Tropical, not yet
reviewed." Per `docs/planning/phase-10-daily-brief-new-today-package/README.md`, the top of the brief
is rebuilt around a new first section, **New Today**.

## Repo-truth discovery (reuse before build)

Existing substrate confirmed and reused (no new ingestion built):

- **Email** — `email_raw_message_structured` (+ recipients child); actionable layer from
  `task_candidates` / `commitment_candidates` (Phase 10 246 follow-up projection).
- **Calendar** — `calendar_raw_event_structured` (+ attendees child).
- **Procore (detail-rich endpoint tables)** — `procore_ep_rfis`, `procore_raw_rfi_responses`,
  `procore_ep_subcontractor_invoices`, `procore_ep_commitment_change_orders`,
  `procore_ep_commitment_contracts` (canonical per memory: live sync → `procore_live_*` / `_ep_`).
- **SharePoint / OneDrive** — `construction_drive_items` (incl. V44 `last_modified_by_display_name`).
- **Refresh markers** — `procore_live_sync_runs`, `email_calendar_raw_ingestion_runs`,
  `construction_source_sync_state`.
- **Project display** — `resources/config/project_aliases.seed.yaml` already carries a `display_name`
  per `project_key`; `construction_project_identity` as a secondary source.

Reused cross-cutting primitives (not re-implemented): `scan_text_for_forbidden` +
`assert_clean_display` (dual output fence), `StructuredOutputClient` / `StaticOutputClient`,
`insert_local_model_run_receipt` + the 13-column `_P10_GUARDS`, `resolve_project`,
`compute_daily_brief_window`, `render_daily_run_html` egress fences.

## Reviewer corrections folded in (the overriding principle)

**New Today is built from business records and source content — never candidate labels / signal
categories.** Plus: bounded local raw context allowed for the model (never persisted/committed/cloud);
email-no-actionable ⇒ degraded; Procore detail-or-drop; refresh-window deterministic contract;
render-model-first; exact fixture-level business assertions; collapsed diagnostics carry no raw keys.
