# 17 — Procore Operational Intelligence (Phase 06B)

Status: **closed (Prompts 00–16)** · Phase 06B (hardening + project-health) · read-only over local SQLite

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

## Freshness / stale-data read model (Prompt 07)

`store/procore_freshness.py::build_freshness_report(project_key, *, now_utc, stale_days=7,
db_path=None)` — deterministic, read-only. Surfaced by
`hb-assistant procore live stale --project KEY [--stale-days N] --json`.

It classifies **every** registry endpoint (`endpoints.list_all()`, 59) for the project:
- **fail_closed** — held (`live_verified=False`) endpoints (the 3). Reported but **excluded** from
  the operational current/stale tally and the stale list, and never given a recommended sync command.
- live-verified endpoints resolve a freshness timestamp by source priority — all written only on a
  successful sync — **watermark** (`procore_live_sync_watermarks.last_success_at_utc`) → latest
  successful **sync run** (`procore_live_sync_runs.completed_at_utc`, state success/partial_success)
  → **record recency** (`max procore_live_records.last_seen_at_utc`):
  - **current** (age ≤ `stale_days`) / **stale** (age > `stale_days`) when a timestamp resolves,
  - **never_synced** when no signal exists at all,
  - **unknown** when a signal row exists but no usable timestamp and no records.

For **stale** + **never_synced** operational endpoints it emits a `recommended_sync_command` (a
string, never executed): `HB_PROCORE_LIVE=1 hb-assistant procore live sync --project {p} --endpoint
{id} --apply --sqlite-only --max-pages 3 --max-items 100 --confirm-live-get --json`. Output carries
`summary` (per-status counts + `operational_total` excluding fail_closed), per-endpoint rows
(status / source / age_days / record_count), `stale_endpoints`, and `no_live_call_performed` /
`no_raw_values_persisted` / `determinations_made: false`. Read-only — no `procore_endpoint_freshness`
table is persisted (no new migration); freshness is derived on demand. Evidence:
`docs/evidence/construction-intelligence-phase-06b-procore-operational-intelligence/07-freshness-and-stale-data-proof.json`.

## Overdue & action queue (Prompt 08)

`store/procore_action_queue.py::build_overdue_queue(project_key, *, now_utc, importance=None,
endpoint_id=None, dimension=None, max_items=50, db_path=None)` — deterministic, read-only.
Surfaced by `hb-assistant procore live overdue --project KEY [--importance I] [--endpoint E]
[--dimension D] [--max-items N] --json`. It reuses
`procore_enrichment.get_procore_action_signals` and the Prompt 06 helpers `_dimensions_for` /
`_parse_iso` (`_DIMENSION_KEYWORDS`) from `procore_project_health`.

**Inputs → one operational queue** (all `project_key`-scoped):
- **open work** — every OPEN `procore_action_signals` row (the queue spine), carrying
  `signal_type`, `importance`, `due_at_utc`, `owner_entity_key` (owner/responsible-party),
  `record_key`, `endpoint_id`, and the signal's own `reason_codes`.
- **due dates** — the signal's normalized `due_at_utc` first; when absent, a best-effort
  fallback reads one normalized date from the canonical record (`procore_live_records.
  canonical_json_redacted`) via an explicit `_DUE_DATE_FIELDS` allowlist (only the normalized
  ISO date is re-emitted — never the raw field value). Each row gets a `status`
  (`overdue` / `upcoming` / `no_due_date`) and, when overdue, `days_overdue`.
- **review flag + source link** — joined from `procore_live_records` on `record_key`
  (`review_required`, `source_url_redacted`); signals with no matching live record degrade
  gracefully (`review_required: false`, `source_url_redacted: null`).
- **exposure (where available)** — `procore_financial_amount_facts` joined on `record_key`,
  surfaced as `exposure_present` + `exposure_amount_names` (distinct NAMES) + `exposure_fact_count`.
  **Amount values are never emitted.**
- **dimensions** — each row classified via `_dimensions_for` (cost / schedule / safety-quality-
  compliance / overdue lenses).

**Output:** `summary` (total_open / overdue / upcoming / no_due_date / high_importance /
review_required / by_dimension), a deterministically ordered `queue` (overdue-first, then
most-overdue, importance, due date, key) with the per-row fields above + derived
`reason_codes` (`past_due_date`, `no_due_date_high_importance`, `overdue_signal_type`,
`review_required_record`), `queue_truncated`, and `unsupported_due_date_endpoints` (endpoints
for which no queued item carried a normalizable due date — the documented stop-condition
surface).

**Guardrail posture:** intelligence/review aid only — no legal/claims/financial/safety/
entitlement/schedule determination (`determinations_made: false`), `no_live_call_performed:
true`, `no_raw_values_persisted: true`. Read-only; no migration/persistence (consistent with
Prompts 06/07). Evidence:
`docs/evidence/construction-intelligence-phase-06b-procore-operational-intelligence/08-overdue-and-action-queue-proof.json`.

## Cost exposure model (Prompt 09)

`store/procore_cost_exposure.py::build_cost_exposure(project_key, *, now_utc, exposure_type=None,
importance=None, max_items=100, db_path=None)` — deterministic, read-only. Surfaced by
`hb-assistant procore live financial exposure --project KEY [--type T] [--importance I]
[--max-items N] --json` (a new verb in the Phase 05 `live financial` group). It reuses
`procore_enrichment.get_procore_action_signals` and the Phase 05 read helpers
`procore_financials.read_financial_amount_facts` / `read_financial_budget_changes`.

**Inputs → exposure types** (all `project_key`-scoped). Open `procore_action_signals` are mapped to
exposure types by an explicit, auditable `signal_type → type` table (`_EXPOSURE_SIGNAL_MAP`); only
cost/financial signal types are mapped (others are skipped). A separate `amount_changed` lens is
read straight from `procore_financial_budget_changes`:
- **pending_change** — `change_event_pending` / `change_event_rom_cost_exposure` /
  `change_event_schedule_impact`.
- **unapproved_change** — `commitment_unexecuted` / `commitment_change_order_unexecuted` /
  `commitment_change_order_unpaid` / `contract_unexecuted`.
- **budget_movement** — `budget_change_posted` / `budget_modification_posted` /
  `budget_variance_negative` / `budget_forecast_exceeds_budget` / `budget_actual_exceeds_budget`.
- **invoice_retainage_risk** — `invoice_approved_not_paid` / `invoice_payment_due` /
  `invoice_retainage_held` / `invoice_pending_approval` / `billing_period_due_soon`.
- **rfq_quote_pending** — `rfq_estimated_cost_exposure` / `rfq_under_review` / `rfq_overdue` /
  `rfq_no_intent_to_quote` / `rfq_estimated_schedule_impact`.
- **compliance_risk** — `commitment_compliance_document_expiring` / `commitment_non_compliant` /
  `commitment_insurance_not_compliant`.
- **amount_changed** — each `procore_financial_budget_changes` row carrying an `adjustment_amount`
  or both `from_amount`/`to_amount` (decimal-safe strings, never differenced).

Each item is enriched from `procore_financial_amount_facts` (by `record_key`) with `amounts`
(`amount_name` / `amount_value` / `currency_iso_code`) and from `procore_live_records` (by
`record_key`) with `source_url_redacted` + `review_required`.

**Output:** `summary` (total / review_required / `by_type` — all seven types keyed / `by_importance`
/ distinct `currencies`), a deterministically ordered `exposure` list (importance → type →
record_key) with per-item `exposure_type`, `source` (`action_signal`|`budget_change`),
`signal_type`, `endpoint_id`, `record_key`, `importance`, `review_required`, `reason_codes`,
`due_at_utc`, `title_redacted`, `source_url_redacted`, and the decimal-safe `amounts`;
`exposure_truncated`; and `amounts_are_strings: true`.

**Guardrail posture:** advisory / review aid only — **no entitlement, liability, claims, or
contractual determination** (`determinations_made: false`); amount values stay verbatim
decimal-safe strings and are **never summed or differenced** (a total would read as a financial
determination — the stop-condition guard). `review_required` is a documented triage label
(high-importance signal OR high-sensitivity type: compliance / unapproved-change /
invoice-retainage), not a decision. `no_live_call_performed: true`, `no_raw_values_persisted:
true`. Read-only; no migration/persistence (schema V19; consistent with Prompts 06/07/08).
Evidence:
`docs/evidence/construction-intelligence-phase-06b-procore-operational-intelligence/09-cost-exposure-proof.json`.

## Schedule exposure model (Prompt 10)

`store/procore_schedule_exposure.py::build_schedule_exposure(project_key, *, now_utc,
exposure_category=None, importance=None, max_items=50, db_path=None)` — deterministic, read-only.
Surfaced by `hb-assistant procore live schedule exposure --project KEY [--type C] [--importance I]
[--max-items N] --json` (a new `live schedule` sub-group). It reuses
`procore_enrichment.get_procore_action_signals`, `procore_project_health._dimensions_for` /
`_parse_iso`, and `procore_action_queue._due_status` / `_canonical_due` / `_record_key` — no new
table or migration (schema stays V19, consistent with Prompts 06–09).

**Inputs → exposure categories** (all `project_key`-scoped). Open `procore_action_signals` from the
schedule-bearing domains are mapped by an explicit, auditable `signal_type → category` table
(`_SCHEDULE_EXPOSURE_SIGNAL_MAP`); signal types absent from it are skipped:
- **overdue_rfi** — `rfi_overdue`. **overdue_submittal** — `submittal_overdue`.
- **critical_or_low_float_activity** — `activity_critical` / `activity_zero_float` /
  `activity_constrained` / `activity_deadline_variance`.
- **meeting_action_topic** — `meeting_topic_open_high_priority`.
- **inspection_punch_blocking** — `inspection_overdue` / `inspection_has_deficient_items` /
  `inspection_has_unanswered_items` / `inspection_open_safety` / `punch_overdue` /
  `punch_due_tomorrow` / `punch_assignment_waiting` / `punch_unresolved_response` /
  `observation_open_safety` / `observation_high_priority`.
- **schedule_impact_flag** — `rfi_schedule_impact_flagged` /
  `submittal_required_on_site_date_near` / `purchase_order_delivery_due` / `observation_due_soon`.

**Due dates** come from the signal's normalized `due_at_utc` first, falling back to a normalized
date extracted from the live record's `canonical_json_redacted` (never the raw field value); each
item is classified `overdue` / `upcoming` / `no_due_date` with `days_overdue` for overdue items.
Each item is enriched from `procore_live_records` (by `record_key`) with `source_url_redacted` +
`review_required`, and carries `dimensions` (`_dimensions_for`).

**Repo-truth note (daily logs):** the package brief lists daily logs in the join set, but no
daily-log projection emits action signals in this repo. Rather than fabricate, `daily_log_delay`
is a declared canonical category (always 0) and is echoed under `unsupported_categories` with a
reason string — the same stop-condition surface style as the overdue model's
`unsupported_due_date_endpoints`.

**Output:** `summary` (total / review_required / overdue / `by_category` — all seven categories
keyed incl. `daily_log_delay` / `by_importance`), a deterministically ordered `exposure` list
(overdue-first → most-overdue → importance → due → record_key → signal_type) with per-item
`exposure_category`, `signal_type`, `endpoint_id`, `record_key`, `due_at_utc`, `status`,
`days_overdue`, `importance`, `owner_entity_key`, `review_required`, `reason_codes`, `dimensions`,
`title_redacted`, `source_url_redacted`; `exposure_truncated`; and `unsupported_categories`.

**Guardrail posture:** advisory / review aid only — **no delay, entitlement, responsibility,
claims, liability, or schedule-impact determination** (`determinations_made: false`). The model
surfaces that a signal *exists*; it never asserts who caused a delay, how many days are owed, or
that a deadline was breached (the stop-condition guard). `review_required` is a documented triage
label (high-importance signal OR high-sensitivity category: overdue RFI/submittal,
critical/low-float activity, inspection/punch/observation blocker, OR a record review flag), not a
decision. `no_live_call_performed: true`, `no_raw_values_persisted: true`. Read-only; no
migration. Evidence:
`docs/evidence/construction-intelligence-phase-06b-procore-operational-intelligence/10-schedule-exposure-proof.json`.

## Responsible party & relationship quality (Prompt 11)

`store/procore_relationship_quality.py` — two deterministic, read-only read models surfaced as two
top-level `live` verbs:
- `build_responsible_party_gaps(project_key, *, now_utc, endpoint_id=None, db_path=None)` →
  `hb-assistant procore live responsible-party-gaps --project KEY [--endpoint E] --json`.
- `build_relationship_quality(project_key, *, now_utc, max_items=50, db_path=None)` →
  `hb-assistant procore live relationship-quality --project KEY [--max-items N] --json`.

It reuses `procore_action_queue._record_key`, `procore_commitment_projection._commitment_exists`,
and the relationship edges emitted by `procore_enrichment.emit_record_edge` /
`procore_financial_projection.link_record_entities`. No new table or migration (schema stays V19).

**Relationship edge map** (operator label → concrete `procore_record_edges.edge_type`,
`_RELATIONSHIP_EDGE_TYPES`): `owner → created_by`, `assignee → assignee`,
`ball_in_court → ball_in_court`, `responsible_contractor → responsible_contractor`,
`vendor → vendor`, `location → at_location`. There is no dedicated Procore "owner" edge; `created_by`
is the concrete owner-proxy and the `owner` label is surfaced explicitly so it never overclaims.

**Responsible-party-gaps** — for each endpoint present in `procore_live_records` (optionally one),
for each relationship: `records`, `records_with_edge` (records whose `record_key` is the
`from_record_key` of ≥1 edge of that type), `missing`, `coverage_pct`, and `status`. Non-guessing
rule: `not_observed` when **no** record carries the edge (the relationship is not asserted to apply);
`partial_gap` only when **some** records carry it and others do not; `covered` when all do. Only
`partial_gap` rows feed `summary.partial_gap_relationships` / `missing_total` — `not_observed` is
never counted as a fabricated gap (stop-condition guard).

**Relationship-quality** — three structural lenses: (1) **orphans** — child records
(`parent_procore_id != ''`) whose `parent_procore_id` is not the `procore_record_id` of any record in
the project, with per-endpoint counts and a capped refs-only sample; (2) **linkage** — `child_records`
/ `children_with_resolved_parent` / `linkage_pct`, reported `unknown` when there are no child records
(never guessed); (3) **duplicate_warnings** — `purchase_order`-family contracts whose `contract_id`
already exists as a `commitment` (via `_commitment_exists`), the only repo-supported dedupe surface.

**Guardrail posture:** data-quality / review aid only — structural metadata, counts, and refs; **no
legal/claims/safety/entitlement determination** (`determinations_made: false`), and linkage that
cannot be inferred is `unknown` rather than guessed. `no_live_call_performed: true`,
`no_raw_values_persisted: true`. Read-only; required-work item 5's optional
`procore_relationship_quality_metrics` persistence is **not** implemented — metrics are derived on
demand (schema stays V19, consistent with Prompts 06–10). Evidence:
`docs/evidence/construction-intelligence-phase-06b-procore-operational-intelligence/11-responsible-party-and-relationship-quality-proof.json`.

## Operational CLI surface (Prompt 12)

Prompt 12 consolidates the Phase 06B read models into a stable operator surface under
`hb-assistant procore live` — every command local SQLite only, read-only, no live call. Seven verbs
already existed (Prompts 06–11); four are new (`store/procore_operational.py`). No name conflicts
(`risks` is a new top-level verb, distinct from the `live financial risk` sub-verb).

| `procore live …` | Read model | New? |
| --- | --- | --- |
| `project-health` | `build_project_health` (P06) | — |
| `stale` | `build_freshness` (P07) | — |
| `overdue` | `build_overdue_queue` (P08) | — |
| `financial exposure` | `build_cost_exposure` (P09) | — |
| `schedule exposure` | `build_schedule_exposure` (P10) | — |
| `responsible-party-gaps` | `build_responsible_party_gaps` (P11) | — |
| `relationship-quality` | `build_relationship_quality` (P11) | — |
| `digest` | `build_operational_digest` — composes the above into a compact headline roll-up | **new** |
| `risks` | `build_risks` — open signals that are high-importance or carry a cost/schedule/safety/overdue dimension | **new** |
| `retrieval-ready` | `build_retrieval_readiness` — preliminary local-corpus probe | **new** |
| `no-writeback-proof` | `build_no_writeback_proof` — preliminary posture attestation | **new** |

`build_operational_digest` and `build_risks` only re-surface existing signals/counts. `digest` calls
each P06–P11 `build_*` and extracts headline numbers (health status, open/high-importance/
review-required, stale, overdue/upcoming, cost/schedule exposure totals, responsibility partial gaps,
orphan records, duplicate warnings). `risks` reuses `get_procore_action_signals` +
`project_health._dimensions_for`.

**Deferral note:** `retrieval-ready` and `no-writeback-proof` are real-but-minimal here so the
surface is contract-stable and JSON-testable; Prompt 14 hardens true embedding readiness
(`content_embeddings`) and Prompt 15 produces the formal no-writeback proof bundle. Both carry a
`note` field stating this.

**Contract tests** (`tests/test_procore_operational_cli.py`): help text asserts local-only/read-only;
JSON-shape + failure-mode (missing `--project`, empty project) per command; and a static AST proof
that the Phase 06B query read-model modules (`procore_operational`, `procore_project_health`,
`procore_freshness`, `procore_action_queue`, `procore_cost_exposure`, `procore_schedule_exposure`,
`procore_relationship_quality`) import no HTTP client (`requests`/`httpx`/`urllib3`/
`procore.http_client`) — extending `tests/test_procore_offline_enforcement.py` to the query sources.
No new table/migration (schema stays V19). Evidence:
`docs/evidence/construction-intelligence-phase-06b-procore-operational-intelligence/12-operational-cli-contract-proof.md`
+ `operational-cli-sample-outputs.json`.

## Obsidian operational outputs (Prompt 13)

`procore/obsidian_operational.py` renders three deterministic, marker-bounded Obsidian notes from the
Phase 06B **local SQLite read models** (never live Procore), mirroring the `obsidian_register.py`
build/`_render_note`/apply pattern and reusing `obsidian._write_procore_artifact` /
`PROCORE_GUARDRAILS` / `ConstructionVaultWriter` and `obsidian_register._table`/`_section`. Surfaced
as three `procore obsidian` verbs — dry-run by default, `--apply` (with `--confirm` non-TTY gate)
writes one marker-bounded note under `vault/01_Projects/` only when the vault is configured
(`HB_CONSTRUCTION_VAULT_ROOT`); unconfigured vault and unparseable `--since` both fail closed.

| `procore obsidian …` | Read models | Marker / file |
| --- | --- | --- |
| `project-health` | `build_project_health` | `HB-PROCORE-OPERATIONAL-PROJECT-HEALTH` → `{project}.procore-project-health.md` |
| `meeting-prep --since` | open action signals (meeting endpoints/`meeting_topic_open_high_priority`) + `procore_live_records` meetings + `build_risks` | `HB-PROCORE-OPERATIONAL-MEETING-PREP` → `{project}.procore-meeting-prep.md` |
| `daily-digest --since` | `build_operational_digest` + `build_overdue_queue` + `build_risks` + `get_procore_changes` (windowed) | `HB-PROCORE-OPERATIONAL-DAILY-DIGEST` → `{project}.procore-daily-digest.md` |

Each note opens with a freshness + review-required **warning banner** and renders only
already-redacted read-model fields (`title_redacted`, counts, status, `due_at_utc`,
`source_url_redacted`, `record_key`) plus a local query-command reference. `review_required` records
are diverted to the warning banner — **never inlined** with sensitive content (stop-condition guard).
No raw payload bodies, signed URLs, or tokens; no determinations. No new table/migration (schema
stays V19). Evidence:
`docs/evidence/construction-intelligence-phase-06b-procore-operational-intelligence/13-obsidian-operational-output-preview.md`
+ `obsidian-operational-dry-run.json`.

## Retrieval readiness (Prompt 14)

Prompt 14 upgrades the Prompt 12 `retrieval-ready` placeholder (`store/procore_operational.py::
build_retrieval_readiness`, surfaced as `procore live retrieval-ready --project KEY [--max-samples N]
--json`) into a **retrieval fact manifest** — retrieval-safe, source-linked Procore facts for local
assistant workflows. Read-only; no new table/migration (schema stays V19). The Prompt 12 corpus
readiness probe (`retrieval_ready` / `reasons` / `corpus`) is preserved alongside the new `manifest`.

**Fact families** (each fact = `fact_type` / `source_table` / `source_key` / `endpoint_id` /
`procore_record_id?` / `attributes` (redacted scalars) / `source_link`):
| Family | Source | Attributes |
| --- | --- | --- |
| `record` | `procore_live_records` (redacted scalar columns) | number, title_redacted, status, updated_at |
| `action_signal` | `get_procore_action_signals` (open) | signal_type, importance, status, due, title_redacted |
| `timeline_event` | `get_procore_changes` (**metadata only**) | detected_at, field_path, change_type/category, importance |
| `exposure` | `build_cost_exposure` + `build_schedule_exposure` items | exposure type/category, importance, due, reason_codes |
| `amount` | `read_financial_amount_facts` | amount_name, amount_value (decimal-safe TEXT), currency |

**No-leak posture (stop-condition guard):** `canonical_json_redacted` free text is never read;
timeline facts **exclude** `old_value_redacted` / `new_value_redacted` / hashes; exposure facts carry
no inline amounts. `review_required` live records are **blocked** (counted under
`blocked_by_reason.review_required`, never emitted). Manifest reports `total_facts`, `by_fact_type`,
`by_endpoint`, `review_required_blocked`, `blocked_by_reason`, and a capped redacted `samples` list;
every fact is source-linked to table/key/record. No raw bodies, signed URLs, tokens, or
determinations (`determinations_made: false`). Evidence:
`docs/evidence/construction-intelligence-phase-06b-procore-operational-intelligence/14-retrieval-readiness-proof.json`.

## No-writeback / no-secret / no-raw-body proof (Prompt 15)

`store/procore_no_writeback_proof.py::build_no_writeback_proof` upgrades the Prompt 12 placeholder
into an **executable proof** (surfaced as `procore live no-writeback-proof --json`) that Phase 06B
added no Procore writeback, no Microsoft 365 writeback, no raw-body persistence, and leaked no
secrets. Read-only; no new table/migration (schema stays V19). The CLI is **fail-closed** (exit 3 if
`proof_passed` is false).

Five checks (`checks_detail`, each `{passed, findings}`):
| Check | What it proves |
| --- | --- |
| `static_writeback_scan` | the 8 Phase 06B modules contain no mutating method calls (`.post(`/`.put(`/`.patch(`/`.delete(`/`.send_mail(`/`.create_message(`…) — call-form only, so prose like "no writeback" never false-positives |
| `no_http_client_imports` | AST: none import `requests`/`httpx`/`urllib3`/`procore.http_client` (query + Obsidian commands cannot call live Procore) |
| `module_secret_scan` | tight value-shaped regexes (JWT, PEM header, `Bearer <token>`, SAS `sig=`, `client_secret":"…`) find no secrets in the modules |
| `sqlite_raw_body_guardrail` | every `raw_body_persisted` table (24, discovered from `sqlite_master`) carries `CHECK(raw_body_persisted = 0)` and stores only `0` |
| `evidence_output_scan` | the phase evidence `*.json` outputs carry no token/secret/signed-URL patterns |

The prover holds the detection patterns, so it deliberately scans the *other* 8 Phase 06B modules,
never itself (a self-scan would false-positive on its own pattern table). Secret scans use
value-shaped regexes, never bare keywords, because the evidence narratives mention "Authorization
headers" / "tokens" in prose. `_scan_text_for_secrets` is unit-tested against planted secrets +
prose so the proof is not vacuous. Evidence:
`docs/evidence/construction-intelligence-phase-06b-procore-operational-intelligence/no-writeback-proof.json`
+ `15-no-writeback-no-secret-no-raw-body-proof.md`.

## Phase 06B closeout (Prompt 16)

Phase 06B is **closed**. The full validation matrix ran end-to-end: `pytest` **1836 passed / 28
failed / 1 skipped** with the Phase 06B operational read-model/CLI/Obsidian/proof tests **100/100
green** and all 28 failures documented as **unrelated** — 17 migration version-assertions broken by a
concurrent `project_identity`/data-quality **V20** migration committed to `main` after the P15 commit
(Phase 06B is read-only and added no migration — schema stays **V19**), 7 pre-existing email-track
failures (`upsert_email_model_classification`, per the Phase 06A closeout), and 4 date-dependent
automation tests (weekend `manual_only` skip). `ruff check .` clean on the Phase 06B + tracked
surface; `mypy src` clean; `compileall` clean; `procore validate` 28/28; the operator commands
(`endpoints list`/`ledger`, `project-health`, `stale`, `digest` — now with an optional `--since`
adding `changes_in_window`, `no-writeback-proof` `proof_passed: true`) all operational; held-endpoint
dispositions final (3 preserved fail-closed); endpoint ledger current; Obsidian outputs marker-bounded
and dry-run-default. No M365/Procore writeback; no raw bodies/secrets; no determinations. Operator
runbook: `docs/runbooks/phase-06b-operational-procore-workflows.md`. Closeout evidence:
`docs/evidence/construction-intelligence-phase-06b-procore-operational-intelligence/`
(`16-final-validation-closeout.md`, `phase-06b-validation-summary.json`,
`phase-06b-commit-message.txt`).
