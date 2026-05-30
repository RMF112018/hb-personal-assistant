# 15 — Procore Second-Brain Enrichment (Phase 04B)

Status: **current** · Phase 04B closed 2026-05-29 · Migration **V7** · 27 endpoints

Phase 04B turns the Phase 04A live-sync (flat latest-state `procore_live_records`)
into a queryable construction **second brain**: per-record history, field-level
change events, an assistant-ready timeline, cross-cutting enrichment (people /
company / location / attachment / custom-field entities, relationship edges,
action signals, text intelligence), read-only query commands, and a deterministic
Obsidian register. Everything stays redacted — no raw payload bodies, no secrets,
no signed-URL query strings.

> **Endpoint coverage & payload contracts (Phase 06B Prompt 05).**
> `procore/coverage.py` reports, per endpoint, what the normalizer does to a payload —
> **names/types/counts only, never raw values**. `compute_payload_coverage` classifies the
> canonical output into `captured_scalar_fields`, `hash_only_fields` (the `*_summary`/`*_ref`
> redacted summaries), `projected_containers` (entities/edges/action_signals/text_intelligence),
> and `intentionally_omitted_fields` (raw fields not carried into the row — some still feed
> projections), and surfaces `normalizer_name` + `normalizer_version`
> (`NORMALIZATION_SCHEMA_VERSION`). `build_coverage_matrix` (CLI `procore live coverage-matrix
> [--payloads-dir]`) aggregates this **by endpoint family**: every endpoint emits a contract row
> (normalizer meta + the documented `_FAMILY_PROJECTION` targets + sensitivity + held status), and
> endpoints with a local sample are enriched with the field-name buckets above. Held endpoints
> with no normalizer (e.g. `budget-details`) report `registered: false`. The matrix is structurally
> raw-value-free, so no payload values ever reach SQLite, Obsidian, logs, or evidence.
## Schema (V7, additive)

`store/migrator.py` V7 adds 18 tables (idempotent; `apply()` returns 7):

- **History:** `procore_live_record_state_index`, `procore_live_record_snapshots`,
  `procore_live_record_change_events`, `procore_record_timeline_events`.
- **Cross-cutting enrichment:** `procore_people_entities` (login/name hashed),
  `procore_company_entities` / `procore_location_entities` (org/place labels kept —
  not PII), `procore_attachment_refs` (path-only + hash; query strings dropped),
  `procore_custom_field_values` (typed; strings hashed), `procore_record_edges`,
  `procore_action_signals`, `procore_text_intelligence` (hash + length + PII-masked
  excerpt + optional Fernet-vault ref).
- **Inspection:** `procore_inspection_records|sections|items|response_sets|
  response_options|evidence_rules`.

`raw_body_persisted = 0` / `redaction_applied = 1` CHECK constraints enforce the
no-raw-body posture at the table level. The text vault
(`security/text_vault.py`, Fernet, `0o600`) stores full text **outside** the repo;
tables hold only the 32-char ref.

## Write path — projections wired in `live_sync.py`

After each per-record latest-state upsert, the parent loop runs guarded
(`try/except` → redacted receipt error, never breaks sync):
`record_procore_history_for_record` (snapshot-if-changed → field diff → change
events → timeline) then the family projection for
`inspections|inspection-sections|inspection-items`, `meetings|meeting-detail`,
`rfis`, `submittals`, `punch-items`, `observations`, `activities`. Daily-log
enrichment runs at the **normalizer layer** (`normalizers/daily_log_live.py` via
`EntityBuilder`). Projections read the raw payload and reuse the
`store/procore_enrichment.py` extractors/emitters.

### Signal / edge catalog (selected)
- inspection: `inspection_open_safety`, `inspection_overdue`,
  `inspection_has_deficient_items`, `inspection_has_unanswered_items`,
  `inspection_item_unanswered`, `inspection_item_non_conforming`.
- observation: `observation_open_safety`, `observation_high_priority`,
  `observation_closed`, `observation_due_soon`.
- rfi: `rfi_open/unanswered/overdue/cost_impact_flagged/schedule_impact_flagged/
  official_answer_added/answered/ball_in_court_changed`.
- submittal: `submittal_open/overdue/rejected/approved/waiting_on_approver/
  required_on_site_date_near/response_returned`.
- punch: `punch_overdue/due_tomorrow/unresolved_response/assignment_waiting`.
- activity (schedule): `activity_critical/zero_float/deadline_variance/constrained`.
- daily-log (normalizer): `daily_delay_reported`, `daily_note_review_required`,
  `daily_manpower_anomaly` (+ `safety`, `delay`, `issue_day`, `weather_delay`).
- edges: `at_location`, `trade`, `vendor`, `assignee`, `approver`, `created_by`,
  `responsible_contractor`, `ball_in_court`, `response_to_rfi`, `in_schedule`,
  `child_of_activity`, `has_topic`, `scheduled_task`, `resource`, `category`, …

History `change_category` values (significance-classified) include
`record_created`, `status_changed`, `closed`, `became_overdue`,
`due_date_changed`, `ball_in_court_changed`, `response_added`,
`inspection_item_became_unanswered`, etc.

## Daily-log date window

`run_live_sync(start_date=…, end_date=…)` adds the date filter to GET params;
exposed as `--start-date` / `--end-date` on `procore live sync` / `live smoke`.
Live evidence: with a 2024→2026 window, Tropical daily logs return 100+ rows where
a no-filter query returned 0 (the prior "zero records" was a missing-filter
artifact).

## Read path — query commands (`cli/procore.py`, local, read-only)

`procore live history|changes|timeline|actions|coverage` query the V7 tables only
(no Procore call). Readers: `get_procore_record_history`, `get_procore_changes`,
`get_procore_timeline` (`store/procore_history.py`), `get_procore_action_signals`,
`get_procore_text_intelligence` (`store/procore_enrichment.py`). Relative-time
parsing via `procore/time_window.parse_since`; field-coverage via
`procore/coverage.compute_payload_coverage` (names/types only). Output carries
source `record_key` / `procore_record_id` + redacted summaries.

## Obsidian register

`procore obsidian enriched` (dry-run default, `--apply` gate) writes one
marker-bounded note `01_Projects/<project>.procore-memory-register.md`
(`procore/obsidian_register.py`) with eight sections (open actions, 48h changes,
inspection unanswered, safety/compliance queue, meeting decisions/actions, RFI
response changes, submittal workflow changes, schedule risk) — redacted columns +
source IDs + a `procore live …` query reference per section.

## Guarantees

Read-only/GET-only; idempotent additive migrations; PII hashed; org/place labels
kept; attachments path-only; free text hashed + vaulted; query commands never call
Procore. Validation at closeout: pytest 1112 passed / 2 skipped, ruff/mypy/
compileall green, `procore validate` 28/28, 27 endpoints live-verified,
scan-sensitive clean on touched files.

Evidence: `docs/evidence/construction-intelligence-phase-04b/00-…12-…`. Operator
usage: `docs/operations/procore-operator-runbook.md`.
