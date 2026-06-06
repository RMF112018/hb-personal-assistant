# 179 — Daily Brief V2 Record-Level Enrichment (Phase 09 Addendum, Prompt 02)

## Context

Prompt 01 split the V2 packet into `render_payload` / `governance_metadata` but left the user-facing
sections as count/aggregate placeholders with honest `data_gaps`. The Prompt 00 baseline flagged
"count-only tables" as a core executive-utility defect. Prompt 02 enforces the **count-vs-detail rule**:
*if the brief reports a count, it must either list the underlying records with useful detail or
explicitly say record-level detail is unavailable — a bare count is never actionable content.*

Scope was deliberately bounded (repo-truth driven): wire **real** records only where a working reader
already exists; declare the typed shape but emit explicit detail-unavailable for Procore domains that
have no dedicated reader yet; and never fabricate fields the store does not persist.

## Design

### Uniform RecordSection + invariant
Every record-bearing section is a `RecordSection`:
`{count, records, detail_available, detail_gap_reason, source_family, why_it_matters, truncated?, total_count?}`.
`_count_detail_ok` (in `packet.py`) is valid iff `count == 0`; OR records present AND
`detail_available` AND `count == len(records)`; OR a positive count with no records AND
`detail_available=False` AND a non-empty `detail_gap_reason`. Truncation is explicit
(`truncated` + `total_count`) — no silent caps. This is what the proof and tests enforce.

### Read-only enrichment layer — `daily_brief/enrichment.py`
`build_record_enrichment(*, brief_date, project_key, db_path, project_keys)` returns the record
sections from stores that already expose safe, redacted, source-linked data:

| Reader | Sections |
| --- | --- |
| `ConstructionStore` calendar (`calendar_event_index` + `calendar_event_attendees`) | `today_agenda`, `yesterday`, `calendar_activity` |
| `ConstructionStore.list_email_thread_summaries` | `email_activity` |
| `build_overdue_queue` (7-day window) | `next_7_days` |
| `get_procore_action_signals` (activity_* signal types) | `schedule` |

Procore record domains without a dedicated reader (`rfis`, `submittals`, `punch`, `procurement`) are
emitted via `_unavailable_section` with `detail_gap_reason="dedicated_reader_not_available"`. The
per-project Procore readers are scoped to the project keys observed in the V1 packet (or the explicit
`--project-key`); with no scope they declare `no_project_scope`.

### Builder wiring — `packet.py`
`build_daily_brief_packet_v2` still builds the canonical V1 packet, derives the observed project keys,
calls `build_record_enrichment`, and `_project_v2_from_v1` overlays the record sections into
`render_payload` alongside the V1-derived `needs_attention` / `focus_recommendations` /
`project_signals`. `data_gaps` is now derived from the actual record sections that declare
detail-unavailable (plus coverage warnings) — no stale "deferred" claims. `_assert_no_raw` backstops
the whole packet.

### Missing-field policy (repo truth)
Responsible-party / vendor **names** are not persisted, so they are emitted `null` with a per-record
`detail_availability` reason (`names_not_persisted_opaque_ids_only`); opaque ids are carried separately
where available. Schedule activity attributes (`activity_id`/`name`/`start`/`finish`/`wbs`) live in the
canonical record, not the action signal, so they are `null` with reason
`activity_attributes_in_canonical_not_signal`. `days_open`/`age` derives only from a real start
timestamp, else `null` + reason. Never fabricated.

### Proof — `build_daily_brief_packet_v2_proof`
Seeds calendar/email/action-signal rows (`_seed_v2_enrichment_db`) so the real sections are non-empty,
then asserts: count-vs-detail invariant holds for every RecordSection; a tampered bare count is
rejected (non-vacuous); detail-unavailable domains are explicit; record details are source-linked; no
raw calendar/email payload (`_assert_no_raw` + no `web_link`/URL + a non-vacuous join-URL probe); no
final-determination language across record text; no external writeback. Writes the V2 evidence bundle.

## Surfaces

- `construction/second_brain/daily_brief/enrichment.py` (new)
- `construction/second_brain/daily_brief/packet.py` (constants, `_count_detail_ok`, builder overlay,
  proof checks, `_seed_v2_enrichment_db`)
- `resources/json/phase_09_daily_brief_handoff_packet_v2_contract.json` (v1.1.0: sections,
  RecordSection shape, per-domain `record_field_specs`, count-vs-detail rule, detail policy)
- `tests/test_phase_09_daily_brief_packet_v2.py`
- `docs/evidence/construction-intelligence-phase-09-addendum-daily-brief-v2/*`

## Guardrails

Read-only, metadata-only, source-linked, no external writeback, no final determinations, fail-closed —
unchanged from V1. Never emits raw calendar/email body, raw subject, email address, Graph/join/signed
URL, token, or header. V1 builder/proof/CLI default + V1 contract remain untouched. The Procore
canonical-record readers for RFIs/submittals/punch/procurement are the natural next step (a later
prompt) to convert those explicit detail-unavailable sections into listed records.
