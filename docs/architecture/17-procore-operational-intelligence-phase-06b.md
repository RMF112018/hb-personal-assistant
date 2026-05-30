# 17 — Procore Operational Intelligence (Phase 06B)

Status: **current** · Phase 06B (hardening + project-health) · read-only over local SQLite

Phase 06B turns the Procore sync/projection layer (Phases 04A/04B/05) into end-user
**operational intelligence**: deterministic, read-only read models over the existing local
SQLite tables (`procore_live_records`, `procore_action_signals`, `procore_record_edges`,
`procore_text_intelligence`, `procore_live_sync_watermarks`, `procore_financial_*`). No live
Procore access, no writeback, no raw payload values, and **no legal/claims/financial/safety/
entitlement/schedule determinations** — every output is a count/label/reference intelligence aid.

## Project health read model (Prompt 06)

`store/procore_project_health.py::build_project_health(project_key, *, now_utc, stale_days=7,
db_path=None, max_items=25)` — deterministic, read-only. Surfaced by
`hb-assistant procore live project-health --project KEY [--stale-days N] --json` (mirrors
`procore live actions`; `SQLiteMigrator().apply()` then read). It reuses
`procore_enrichment.get_procore_action_signals` and `store.connection.get_connection`.

**Inputs → dimensions** (all `project_key`-scoped):
- **freshness** — `procore_live_sync_watermarks.last_success_at_utc`; an endpoint is `stale` when
  its age exceeds `stale_days` (or `never_synced`).
- **open work / cost / schedule / safety-quality-compliance / overdue** — counts of OPEN
  `procore_action_signals` classified by `signal_type` via documented keyword sets
  (`_DIMENSION_KEYWORDS`). A signal may match multiple lenses; counts are per-dimension and are
  **never summed into one opaque score**. A transparent `dimension_signal_breakdown`
  (`{dimension: {signal_type: count}}`) accompanies the counts.
- **review-required** — `procore_live_records WHERE review_required = 1` (count + an explicit
  `review_required_items` list of endpoint_id / procore_record_id / sensitive_reason /
  source_url_redacted, capped at `max_items`).
- **relationship quality** — `records_missing_responsibility_edge` (records with no
  responsible_contractor/assignee/ball_in_court edge in `procore_record_edges`) and
  `distinct_responsible_parties`.

**Output:** `score_components` (the per-dimension counts), `counts` (totals incl. a COUNT-only
`financial_amount_facts`), `top_risks` (high-importance OR exposure/overdue/safety OPEN signals —
explicit), `stale_endpoints`, `review_required_items`, `evidence_references`
(source_url_redacted pointers), and a deterministic triage `health_status` label
(`no_data` / `review_recommended` / `monitor` / `current`) with a `status_reason` trigger list.

**Guardrail posture:** review-required and high-risk facts are always listed explicitly — never
hidden behind the `health_status` label (a triage aid, not a determination). `determinations_made:
false`, `no_live_call_performed: true`, `no_raw_values_persisted: true`. The command is read-only;
no snapshot is persisted (no new migration). Evidence:
`docs/evidence/construction-intelligence-phase-06b-procore-operational-intelligence/06-project-health-read-model-proof.json`.
