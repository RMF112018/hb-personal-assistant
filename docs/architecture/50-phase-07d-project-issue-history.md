# 50 — Phase 07D: Project Issue History

**Status:** Implemented (Phase 07D Prompt 07). Additive over schema **V25** (no migration).
**Scope:** Materialize `project_issue_history_items` (shipped empty in Prompt 02) by grouping the
unified cross-source substrate into per-issue families using **deterministic + strong-heuristic
relationships only**, via a new `construction-agent issue-history build/status` sub-app. Advisory,
read-only, no raw content, no external writeback, no auto-promotion.

## Problem

The V25 issue-history table had no producer; the meeting-prep brief's `aging_items` section is an
honest deferred placeholder pointing at it. This prompt turns the substrate into bounded, source-
linked issue families with real (best-effort) activity/status.

## Design

### Engine — `construction/issue_history/issue_history_builder.py`

`IssueHistoryBuilder(store)` mirrors the Prompt 06 `MeetingPrepBriefBuilder`. `build(*, dry_run=True,
project_filter=None, now_utc=None)` returns `{command, mode, ok, schema_version, contract_version,
project_filter, summary{projects, families_planned/written, review_required, resolved_activity,
unresolved_activity, by_confidence_class, by_status, by_issue_kind}, guardrails}`. Dry-run plans and
writes nothing; `--apply` upserts. `project_issue_history_status()` is a read-only coverage report.

**Grouping (key decision):** an issue family is **one per distinct anchor source record**
`(source_family, source_record_ref)` that has ≥1 eligible edge — not a transitive connected component.
Component-merging would collapse the project into mega-families through shared entities (`vendor`,
`created_by`, `category`); the per-anchor unit is bounded and deterministic (the natural RFI / change
order / commitment). Live result: 598 families for `tropical`, not one giant blob.

**Eligible edges:** candidates with `confidence_class ∈ {deterministic, strong_heuristic}` and not
`sensitive_high_impact` and not `model_proposed`. Weak / model / sensitive edges are excluded from
grouping entirely — never grouped, never promoted.

**Per family:**
- `issue_family_id = hash_value("issue|{project}|{source_family}|{source_record_ref}")` (idempotent).
- `source_families_json` = sorted distinct families across the family's edges.
- `confidence_class` = `deterministic` iff all member edges deterministic, else `strong_heuristic`.
- `review_required` = any member-edge review flag OR `confidence_class != deterministic` (strong-
  heuristic families stay advisory/review-required).
- `evidence_trail_id` = representative member edge's trail id.
- `issue_kind` = procore endpoint segment of the record_key, else `source_record_type`.

**Activity / status (best-effort honest):** a `{record_key → (updated_at_utc, status)}` map is built
once from `list_procore_live_records()` (record_key reconstructed as `project|endpoint|parent|id`,
matching the substrate `source_record_ref`). For a resolved procore anchor → real `updated_at_utc`
+ a normalized status token + `age_days = max(0, (now − activity).days)` (`now_utc` injectable for
tests). When unresolved (non-procore anchor or missing timestamp) → `latest_activity_utc=NULL`,
`status="unknown"`, `age_days=0`, with `stale_unknown_flags_json` set (`no_source_activity_timestamp`
/ `status_unresolved`). Never fabricated or overstated. Live: 522 resolved / 76 flagged.

**Status normalization (`_normalize_status`):** Procore statuses arrive as messy dict-strings
(`{'id': 20577, 'name': 'Open', 'mapped_to_status': 'open'}`). These are parsed (regex on
`mapped_to_status`/`name`) and mapped to a bounded safe token (open/closed/approved/draft/void/…/
other/unknown) — the raw payload is **never persisted**.

### Store — `construction/store/repositories.py`

`upsert_project_issue_history_item`, `list_project_issue_history_items`,
`count_project_issue_history_items` — mirroring the Prompt 06 brief methods; the eight guard
`CHECK(… = 0)` columns are never written.

### CLI — `construction-agent issue-history`

`build` (`--apply` default dry-run, `--project`, `--json`) and `status` (`--project`, `--json`),
mirroring the `meeting-prep` sub-app.

### Not changed

No prerequisite gate / no policy seed (none exists; the objective is materialization). The meeting-
prep brief is untouched — `aging_items` stays a deferred placeholder (Prompt 09 wires consumption).
`project_issue_history_items` was already registered in `table_lifecycle_status_contract.json`, so
the inventory count stays 120.

## Guardrails

Local-first, read-only. Items persist only counts, enums, bounded status tokens, local record-keys /
hashes, and family names — never raw bodies/text/calendar payloads, raw status payloads, signed/
download URLs, tokens, secrets, prompts, or responses (no-raw-content regex test). Advisory only —
no final legal/contractual/claim/safety/financial determination. Weak/model/sensitive excluded and
never auto-promoted; strong-heuristic families stay review-required.

## Validation

ruff / `mypy src` (182 files) / compileall clean; pytest **2182 passed** (+9 new tests). Live
`issue-history build --apply` materialized **598** `tropical` families (562 deterministic / 36 strong
review-required; 522 activity-resolved / 76 stale-flagged; status tokens all bounded and clean);
dry-run wrote nothing; `issue-history status` reflects it. Both no-writeback proofs pass;
`table-inventory` 25 / 120; `meeting_prep_readiness_claim=ready` unchanged.

## Files

- `src/hb_assistant/construction/issue_history/__init__.py`, `…/issue_history_builder.py` (new).
- `src/hb_assistant/construction/store/repositories.py` (+3 methods).
- `src/hb_assistant/cli/construction.py` (`issue-history` sub-app).
- `tests/test_issue_history.py` (new).

See `docs/evidence/construction-intelligence-phase-07d-cross-source-meeting-prep/07-project-issue-history.md`.
