# 71 — Phase 08A No-Writeback / No-Secret / No-Raw-Content Proof

Status: implemented (Phase 08A Synthesized Prompt 15). Builds on records 57–70.

- Read-only, offline, fail-closed safety prover; reuses the established
  `construction/data_quality/safety.py` scanner helpers; persists nothing; schema/contract
  count unchanged (V26 / 141).

## Purpose

Provides `second-brain data-quality no-writeback-proof`: a formal proof that the Phase 08A
second-brain runtime performs no external-system writeback and persists no secrets / raw
content. It covers the 08A module source, the 18 V26 second-brain tables' guard columns +
persisted content, the Phase 08A evidence tree, the generated daily-brief + delivery-handoff
outputs, and the model-call receipt structure (metadata-only). Parallel to the legacy
`construction-agent data-quality no-writeback-proof` (07A–07D), which is unchanged.

## Repo-truth reconciliation (decisive)

- **No schema change.** The proof is read-only and persists nothing; it applies the
  idempotent migrator only to make the guard-column probe deterministic (additive DDL — the
  same posture every second-brain module uses). Schema stays V26 / 141 tables.
- **Reuses the scanner.** Imports `_scan_module_set`, `_probe_table_guards`,
  `_scan_table_contents`, `_scan_evidence_outputs`, `_scan_obsidian_outputs`,
  `_get_git_sha`, `_get_schema_version`, `_now` from `data_quality/safety.py`, and
  `_scan_text_for_secrets` from its source (`store/procore_no_writeback_proof.py`). No
  duplicated scanner logic.
- **Model boundary disclosed.** The one writeback verb in `second_brain/` —
  `reasoning.py` `client.messages.create(...)` — is the lazy, opt-in, test-never Anthropic
  model call. It is disclosed and excluded from the source-system-writeback aggregation (it is
  the model boundary, not external writeback); the module itself has no bad imports / secrets,
  and model receipts are proven metadata-only.
- **Receipts in-memory only.** No model-call / agent-run receipt table exists (V27-deferred);
  the proof asserts their absence and that `build_model_call_receipt` carries only hashes +
  token counts.
- **Fail-closed.** Any writeback verb (outside the boundary), bad import, missing guard CHECK,
  guard value != 0, absent expected table, or secret/raw finding in code / tables / evidence /
  generated outputs / receipts fails the proof.

## Code

- `construction/second_brain/safety.py` — `build_second_brain_no_writeback_proof(*, db_path)`
  + helpers `_enumerate_second_brain_modules` (dynamic — covers new modules),
  `_derive_guard_map` (derives guard columns from each table's CREATE SQL; fail-closed on
  absent expected table), `_check_model_receipt_metadata_only`, `_scan_generated_outputs`
  (in-memory dry-run brief + handoff). Returns the proof report (command/ok/proof_passed/
  scanned_modules/model_boundary/checks_detail/guardrails/stop_conditions/…).

## CLI

`hb-assistant second-brain data-quality no-writeback-proof [--json]` — emits the proof; exit 0
when `proof_passed`, else 3.

## Guardrails

Read-only, offline, fail-closed. Findings are pattern labels + `table.column` / file locations
only — never the offending value. No external systems touched, no writeback, no live calls.

## Evidence

`docs/evidence/construction-intelligence-phase-08a-second-brain-runtime/`:
`agent-no-raw-content-proof.md`, `agent-no-writeback-proof.md`,
`no-external-writeback-proof.md` (+ `second-brain-no-writeback-proof.json`,
`proof_passed: true`; 51 modules, 18 tables, 10 checks all passed).
