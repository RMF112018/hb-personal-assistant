# Phase 10A Candidate Review CLI — Final Validation & Handoff

**Date:** 2026-06-08
**Package:** HB Construction Intelligence — Phase 10A Candidate Review CLI Implementation Package
**Prompts:** 00–10 · **Versions:** v1.3.0–v1.11.0 · **Base:** `2a045d2f` → **HEAD:** `46cf35a0`
**Scope:** local-first operator triage of persisted task/commitment candidates via
`hb-assistant second-brain review …`. Review actions are local SQLite updates only.

---

## 1. Validation matrix (required commands)

| Command | Result |
|---|---|
| `python -m compileall src tests` | **OK** |
| `mypy src/hb_assistant/construction/second_brain` | **Clean** — 152 source files, no issues (`candidate_review.py` is in the strict scope) |
| `pytest <9 phase-10a/10/08d/second-brain files>` | **131 passed, 0 failed** (23.7s) |
| `ruff check src/.../second_brain src/.../cli tests` | **5 errors — all pre-existing, unrelated to this package** (see §1a) |

### 1a. Broad `ruff check` — disclosed pre-existing validation debt

The broad-scope ruff command exits non-zero due to **5 errors in modules this
package never touched**:

| File:line | Rule | Module |
|---|---|---|
| `src/hb_assistant/cli/procore.py:696` | B008 | Procore CLI |
| `src/hb_assistant/cli/procore.py:1088` | B008 | Procore CLI |
| `src/hb_assistant/cli/procore.py:1729` | B008 | Procore CLI |
| `src/hb_assistant/construction/second_brain/mcp/wrappers.py:214` | F841 (unused `pv`) | MCP wrappers |
| `tests/test_calendar_event_indexing.py:460` | SIM222 (`… or True`) | Calendar test |

These are **pre-existing** (none appear in this package's changed files — see §4) and
are left untouched per surgical-scope / do-not-broaden-scope. They are trivially
fixable by whatever task owns those modules. They are **not** a failure of this
implementation package.

**Scoped ruff over this package's changed code → clean:**
```
ruff check src/hb_assistant/construction/second_brain/local_ai/candidate_review.py \
           src/hb_assistant/cli/second_brain.py \
           tests/test_phase_10a_candidate_review.py \
           tests/test_phase_10a_candidate_review_cli.py
=> All checks passed!
```
(`repositories.py`, `migrator.py`, and the touched test files were ruff-clean at each
commit; `migrator.py`/`repositories.py` are not in ruff strict scope.)

## 2. Acceptance checklist (package §18)

### Functional
- [x] `review list` works for pending candidates — `test_review_list_cli_and_status_filter`, `02-cli-review-evidence.md §3`.
- [x] `review show` includes source refs / evidence redacted only — `test_review_show_cli_found_and_not_found`, evidence §4.
- [x] `review accept` updates local review status + writes event — `test_review_accept_cli_transitions_and_audits_and_preserves_refs`.
- [x] `review ignore` → stored `suppressed` + writes event — `test_review_ignore_cli_normalizes_to_suppressed`.
- [x] `review reject` updates status + writes event — `test_review_reject_cli_with_reason`.
- [x] `review summary` returns grouped counts — `test_review_summary_cli`.
- [x] `review snooze` works (V43 implemented) — `test_review_snooze_cli_and_bad_until`.
- [x] `review edit` works (V43 implemented) — `test_review_edit_cli_records_changes_and_preserves_status_and_refs`.
- [x] `review export` writes redacted JSON — `test_review_export_cli_to_file_and_stdout`.
- [x] Batch defaults to dry-run, requires `--apply` — `test_review_batch_accept_dry_run_then_apply`.

### Safety
- [x] No raw prompt/body/response in CLI output — `test_no_forbidden_keys_in_any_output`, `test_review_*_no_raw_keys`.
- [x] No external writeback — `test_candidate_review_and_cli_import_no_external_write_surface` + repo-wide `test_second_brain_no_writeback_proof`.
- [x] Guard columns remain zero — `test_guardrail_columns_stay_zero_after_review_ops`; evidence §6 (SQL sum = 0 across 4 tables).
- [x] Source refs remain intact — accept/edit source-ref-immutability assertions.
- [x] Stable keys unchanged — `test_store_update_candidate_fields_whitelist` (whitelist excludes `stable_key`).
- [x] Existing extraction commands still work — `test_phase_10a_batch_extraction`, `test_phase_10a_raw_action_intelligence`, `test_phase_10a_packet_extraction_safety` all pass in the matrix.

## 3. Claim discipline (package §17)

**Validated against synthetic / seeded local SQLite DBs only** — NOT the populated
dev DB. This package makes **no** claim about: an exact persisted count (e.g. 21);
the migration having run on production; snoozed candidates being hidden from any UI;
accepted candidates being safe for automation; semantic candidate quality; review
events having captured prior (pre-update) actions; frontend consumption of review
statuses; or any external system being updated.

**What is proven:** the CLI can list/show/summarize persisted candidates, update
local review status, and write local review events; outputs are redacted/safe per
tests; the no-raw / no-writeback proofs pass.

## 4. Changed files (base `2a045d2f` → HEAD `46cf35a0`)

Production code:
- `src/hb_assistant/store/migrator.py` — V43 additive migration (snooze/edit/audit columns; version-gated).
- `src/hb_assistant/construction/store/repositories.py` — candidate read/update API + audit-insert drift fix.
- `src/hb_assistant/construction/second_brain/local_ai/candidate_review.py` — review service (new).
- `src/hb_assistant/cli/second_brain.py` — `second-brain review` verbs.

Tests:
- `tests/test_phase_10a_candidate_review.py` (new), `tests/test_phase_10a_candidate_review_cli.py` (new),
  `tests/test_phase_10_schema.py` (V43 columns), `tests/test_phase_10a_raw_content_review.py` (renamed method call).

Docs/evidence: `README.md`, `docs/architecture/00-README.md`, `docs/architecture/223`–`231`,
`docs/runbooks/phase-10a-candidate-review-cli-runbook.md`,
`docs/evidence/construction-intelligence-phase-10a-candidate-review-cli/00`–`03`.

Commit series: v1.3.0 (rebaseline) → v1.3.1 (V43) → v1.4.0 (service) → v1.5.0 (store API + drift
fix) → v1.6.0 (read CLI) → v1.7.0 (action CLI) → v1.8.0 (snooze/edit/export/batch) → v1.9.0 (test
suite) → v1.10.0 (no-raw/no-writeback proofs) → v1.11.0 (docs/runbook/evidence) → this closeout.

## 5. Deferred / open items

- **Pre-existing ruff debt** (§1a) in `cli/procore.py`, `mcp/wrappers.py`,
  `test_calendar_event_indexing.py` — out of this package's scope.
- **Pre-existing test failure** `test_phase_10_email_task_extraction.py::test_commitment_persists_to_commitment_table`
  fails on clean `main` (verified by stashing during v1.4.0) — unrelated, and **not**
  part of this package's validation matrix.
- The repo's pre-existing dirty file
  `docs/evidence/construction-intelligence-phase-08b-automation-hardening/phase-08b-final-no-writeback-proof.md`
  was left untouched throughout (never staged).
- Follow-on work (UI integration, downstream automation, semantic-quality tuning) is
  explicitly a **new** phase, not unfinished Candidate Review CLI delivery.

## 6. Handoff (per template §21)

See the final response. Summary: implemented the Phase 10A candidate review CLI for
local task/commitment candidates; review actions are local DB updates only with a
`candidate_review_events` audit trail; no raw content and no external writeback;
guard columns remain zero.
