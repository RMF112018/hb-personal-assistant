# 55 — Phase 07D: Data Quality Gates

**Status:** Implemented (Phase 07D Prompt 12). Additive over schema **V25** (no migration).
**Scope:** Complete the 07D gates wiring — a new `data_quality/phase_07d.py` assembles the full
twelve-field `phase_07d_data_quality_gates.json` conformance report, the OneDrive/SharePoint
source-scope gate emits four named **safe counts**, and `construction-agent data-quality
phase-07d-gates --json` exposes it (the command the `phase_07d_validation_matrix` already references).
Read-only, no raw content, nothing auto-promoted.

## Design

### Engine — `construction/data_quality/phase_07d.py`

`evaluate_phase_07d_data_quality_gates(*, db_path=None) -> dict` assembles all twelve contract fields:
- **Five prerequisite gates** (Prompt 05) reused via `evaluate_data_quality_gates(persist=False)` —
  no duplication. `phase_07d.py` imports `gates.py` one-way (no cycle).
- **Four coverage gates** over the V25 read models (meeting-prep brief / issue history / risk digest /
  aging exposure): `count>0 → pass`, `0 → deferred_not_blocking` (never overstated as pass on empty).
- **`obsidian_output_safety`**: guard-column sum of `cross_source_intelligence_obsidian_runs` == 0
  with runs present → pass; no runs → deferred; guard>0 → fail_blocking.
- **`stale_unknown_warning_coverage`**: stale/unknown warnings surfaced (issue/risk
  `stale_unknown_flags_json`; aging `missing_status_flag` / unknown band) → pass; no source rows →
  deferred.
- **`no_writeback_no_secret_no_raw_content_proof`**: a 07D-scoped scan of all ten V25 tables — the
  eight guard `CHECK(…=0)` columns sum to 0 **and** a forbidden-pattern (`%http%` / `%token=%` /
  `%bearer %` / `%-----begin%`) LIKE-count over each table's safe text columns is 0 → `proof_passed`;
  any violation → fail_blocking.

Report: `{command, ok, schema_version, contract_version, generated_utc, gates[12], by_field_status,
required_fields_covered, source_scope_safe_counts, no_writeback_proof{proof_passed, guard_violations,
pattern_hits, tables_scanned}, meeting_prep_readiness, phase_07d_intelligence_ready,
review_required_total, guardrails, stop_conditions_checked}`. `ok` = no `fail_blocking` field.

### Source-scope safe counts

`gates.source_scope_safe_counts(sources)` derives four counts from the
`evaluate_source_scope_compliance` `sources[]` (counts only — never folder names, paths, web URLs,
drive IDs, or item IDs):
`onedrive_explicit_subset_sources` (scope_type `selected_folders`),
`onedrive_explicit_all_folders_sources` (scope_type `all_folders_explicit`),
`onedrive_implicit_root_blocked_sources` (onedrive + `non_compliant`),
`sharepoint_approved_all_nested_sources` (sharepoint + `compliant`). **Explicit all-folders selection
is counted as compliant — never misclassified as blocked.** `_gate_meeting_prep_prerequisite_status`
attaches these to its result so the existing `data-quality gates` output surfaces them too (the only
change to `gates.py`; no gate added/removed, statuses unchanged).

### CLI / contract

`@data_quality_app.command("phase-07d-gates")` → the evaluator → exit `0 if report["ok"] else 1`.
The contract gains an additive `source_scope_safe_counts` field list (required_fields/guardrails
unchanged; table inventory stays 120). The `phase-07d-no-writeback-proof` command stays for Prompt 13.

## Guardrails

Local-first, read-only; persists nothing. Counts/enums only — no raw folder names, paths, URLs, drive
IDs, item IDs, tokens, or secrets in the report (no-raw-content test). Coverage gates defer (never
pass) on empty data — readiness is never overstated. Weak/model/sensitive remain review-required and
are never auto-promoted (the routing gate fails on a misrouted sensitive candidate).

## Validation

ruff / `mypy src` (190 files) / compileall clean; pytest **+8 new tests**; existing gate tests
unchanged. Live `data-quality phase-07d-gates` reports all twelve fields with the four safe counts;
`data-quality gates` `meeting_prep_prerequisite_status` carries `source_scope_safe_counts`; both
no-writeback proofs pass; `table-inventory` 25 / 120; `meeting_prep_readiness_claim=ready` unchanged.

## Files

- `src/hb_assistant/construction/data_quality/phase_07d.py` (new).
- `src/hb_assistant/construction/data_quality/gates.py` (`source_scope_safe_counts` helper + gate refinement).
- `src/hb_assistant/construction/data_quality/__init__.py` (export).
- `src/hb_assistant/cli/construction.py` (`data-quality phase-07d-gates`).
- `src/hb_assistant/resources/json/phase_07d_data_quality_gates.json` (additive safe-count field names).
- `tests/test_phase_07d_data_quality_gates.py` (new).

See `docs/evidence/construction-intelligence-phase-07d-cross-source-meeting-prep/12-07d-data-quality-gates.md`.
