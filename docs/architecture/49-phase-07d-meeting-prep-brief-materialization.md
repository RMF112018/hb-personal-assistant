# 49 — Phase 07D: Meeting-Prep Brief Materialization

**Status:** Implemented (Phase 07D Prompt 06). Additive over schema **V25** (no migration).
**Scope:** Materialize source-linked, review-controlled meeting-prep briefs into the two V25 tables
`meeting_prep_brief_runs` + `meeting_prep_brief_sections` (shipped empty in Prompt 02), via a new
`construction-agent meeting-prep build/status` CLI sub-app. Advisory only, prerequisite-gated, no
raw content, no external writeback.

## Problem

Prompts 02–05 built the V25 cross-source substrate and the meeting-prep prerequisite gates, but the
brief tables had no readers/writers and no producer. This prompt turns the substrate into per-project
briefs whose sections carry confidence labels, evidence refs, and review/stale warnings.

## Design

### Engine — `construction/meeting_prep/brief_builder.py`

`MeetingPrepBriefBuilder(store)` mirrors the `CrossSourceRelationshipSubstrateBuilder` shape.
`build(*, dry_run=True, project_filter=None, lookahead_days=None, now_utc=None, readiness=None)`
returns a report `{command, mode, ok, schema_version, contract_version, policy_version,
lookahead_days, prerequisite_readiness, summary{projects, runs_planned/written,
sections_planned/written, review_required, blocked, by_section_kind}, guardrails}`. Dry-run plans
counts and writes nothing; `--apply` upserts one brief run + its sections per project. Policy/contract
load via `load_phase_07d_seed("meeting_prep_brief_policy")` /
`load_phase_07d_contract("meeting_prep_brief_contract")`.

**Idempotency:** `brief_run_id = hash_value("meeting_prep|{project_key}|{lookahead}")`,
`section_id = hash_value("{brief_run_id}|{section_kind}")` — re-running upserts the same rows.
`now_utc` defaults to `datetime.now(timezone.utc)` and is injectable for deterministic tests.

**Project discovery:** distinct `project_key` from the substrate
(`list_cross_source_relationship_candidates` + `list_cross_source_relationships`), because
`construction_project_identity` is currently empty. `--project` narrows to one.

### Prerequisite gating

`build()` reads `meeting_prep_readiness` from `evaluate_data_quality_gates(persist=False)` (Prompt 05).
When policy `require_prerequisite_gates` is true and readiness is not `ready`, each project run is
written with `status="blocked"` and **zero sections** (`summary.blocked=True`, `ok=True` — a blocked
brief is an honest outcome, not an error). A `readiness: Optional[dict]` injection seam (the CLI never
sets it) lets tests exercise the materialization path without standing up all 21 upstream gates.

### Eight sections (policy `sections`)

Each section row carries a redacted compact-JSON summary (counts / enums / local identifiers only), a
confidence class (V25 enum, NOT NULL), an optional evidence-trail ref, a review flag, and
stale/unknown flags:

| Section | Source | Notes |
|---|---|---|
| `meeting_context` | `list_calendar_event_index`, lookahead-filtered | project-matched count + flagged unmatched-upcoming count; live calendar is unmatched (`project_key=NULL`) so this is honestly empty-with-warning |
| `project_context` | `get_project_identity` | `None` → `identity_resolved:false` + `unknown_project_identity` flag; never copies `project_name_raw` |
| `open_items` | candidates (project-scoped) | counts by relationship_type + confidence_class |
| `aging_items` | — | **deferred** (`project_issue_history_items` empty; Prompt 07/09) — `deferred_source` flag, no fabricated items |
| `recent_activity` | promoted `cross_source_relationships` | counts by family/type |
| `risk_exposure_watchlist` | — | **deferred** (`project_risk_digest_items` empty; Prompt 08) |
| `review_required_warnings` | candidates with `review_required=1` | safety surface; counts by type |
| `confidence_and_stale_unknown_warnings` | weak/model/stale candidates + evidence-trail stale flags | |

`meeting_prep_brief_status(store, project_filter=None)` is a read-only coverage report
(`runs / sections / blocked_runs / materialized_runs / review_required_sections / by_section_kind`).

### Store methods — `construction/store/repositories.py`

`list_cross_source_relationships(*, project_key=None, limit=2000)` (promoted reader; only `count`
existed) plus `upsert_meeting_prep_brief_run`, `upsert_meeting_prep_brief_section`,
`list_meeting_prep_brief_runs`, `list_meeting_prep_brief_sections`, `count_meeting_prep_brief_runs`,
`count_meeting_prep_brief_sections` — mirroring `upsert/list_source_evidence_trail`. The eight guard
`CHECK(… = 0)` columns are never written (schema defaults hold).

### CLI — `construction-agent meeting-prep`

`build` (`--apply` default dry-run, `--project`, `--lookahead-days`, `--json`) and `status`
(`--project`, `--json`), mirroring the `relationships` sub-app.

## Guardrails

Local-first, read-only. Sections copy only counts, enum classes, `project_key`, local ids/hashes, and
already-redacted labels — never raw bodies/text/calendar payloads, signed/download URLs, tokens,
secrets, prompts, or responses (no-raw-content regex test over the serialized run+sections). No final
legal/contractual/claim/safety/financial determination language (policy `forbidden_outputs`). Weak/
model/sensitive relationships stay review-required; nothing is auto-promoted. No schema change, no
external writeback.

## Validation

ruff / `mypy src` (180 files) / compileall clean; pytest **2173 passed** (+8 new tests). Live
`meeting-prep build --apply` materialized one `tropical` run with all eight sections (3 review-required
surfaced); dry-run wrote nothing; `meeting-prep status` reflects it. Both no-writeback proofs pass;
`table-inventory` 25 / 120; `meeting_prep_readiness_claim=ready` unchanged.

## Files

- `src/hb_assistant/construction/meeting_prep/__init__.py`, `…/brief_builder.py` (new).
- `src/hb_assistant/construction/store/repositories.py` (1 promoted-relationship reader + 6 brief methods).
- `src/hb_assistant/cli/construction.py` (`meeting-prep` sub-app).
- `tests/test_meeting_prep_brief.py` (new).

See `docs/evidence/construction-intelligence-phase-07d-cross-source-meeting-prep/06-meeting-prep-brief-materialization.md`.
