# Phase 08C — No-Writeback / No-Raw-Financial-Output Safety Proof

Design record for the Phase 08C extension of the second-brain no-writeback safety proof.
Read-only, deterministic, fail-closed. Repo code, tests, and evidence are authoritative.

## Purpose

Extend the deep second-brain safety scan (`build_second_brain_no_writeback_proof`) over the
Phase 08C surface — its financial modules, its ten V35 tables, and its evidence directory (where the
read-only operator CLI surfaces persist their outputs) — and emit a dedicated
`no-writeback-no-raw-financial-output-proof.json`.

This is distinct from Prompt 10's `financial-no-writeback-proof.json` (a *data-level* attestation:
guard columns + money-not-float + evidence redaction + no-live). This proof is the *code + data +
evidence* safety scan.

## Builder — `build_phase_08c_no_writeback_no_raw_financial_output_proof`

`construction/second_brain/safety.py`. Reuses the battle-tested 08A/08B scan helpers (no new
scanners) and runs four checks:

- **`static_mutation_scan_08c_modules`** — `_enumerate_second_brain_modules` filtered to the 08C
  financial set (`financial_completeness`, `financial_amount_normalization`,
  `financial_review_routing`, `financial_no_writeback`, `data_quality`, `contracts`) → `_scan_module_set`;
  flags mutation verbs (`.post/.put/.patch/.delete/...`), dangerous imports (requests/httpx/aiohttp/
  procore/msgraph/msal), and secrets.
- **`guard_column_probe_08c_tables`** — `_derive_guard_map(conn, _PHASE_08C_TABLES)` (now parameterized)
  + `_probe_table_guards`; fail-closed on any absent table or missing/violated `=0` guard.
- **`content_leak_scan_08c_tables`** — `_scan_table_contents` over the ten V35 tables.
- **`evidence_raw_secret_scan_08c`** — `_scan_evidence_outputs(repo_root,
  "construction-intelligence-phase-08c-financial-readiness")`.

### Confirmations (operator-facing)
A `confirmations` dict of six booleans, each backed by the relevant guard column declared `=0`
across every present table plus the relevant clean scan:
`no_external_writeback`, `no_procore_mutation`, `no_raw_financial_source_payload`,
`no_raw_prompts_or_responses`, `no_signed_or_download_urls`,
`no_payment_or_claim_or_entitlement_decisions`.

`proof_passed = modules_ok AND guards_ok AND content_ok AND evidence_ok AND all(confirmations)`.

Writes `no-writeback-no-raw-financial-output-proof.json` (+ `.md`) to the 08C evidence dir. Findings
record locations/labels only (e.g. `file: <pattern-label>`, `table.column: <label>`), never the
offending value. `_derive_guard_map` was refactored to accept an optional `tables` argument
(default `_PHASE_08A_TABLES`), leaving the broad 08A/08B proof unchanged.

## CLI

`hb-assistant second-brain data-quality phase-08c-no-writeback-proof [--json/--no-json]` runs the
builder, surfaces `proof_passed` / per-check pass / confirmations / `proof_path`, and exits `0` on
pass, `3` on fail (**fail-closed** — stop if the proof fails).

## Files

- `src/hb_assistant/construction/second_brain/safety.py` — `_PHASE_08C_TABLES`,
  `_PHASE_08C_MODULE_BASENAMES`, `_PHASE_08C_ZERO_GUARDS`, `_derive_guard_map(tables=...)`,
  `build_phase_08c_no_writeback_no_raw_financial_output_proof`, `_render_phase_08c_no_writeback_md`.
- `src/hb_assistant/cli/second_brain.py` — `data-quality phase-08c-no-writeback-proof` command.
- `tests/test_phase_08c_no_writeback_proof.py` — clean pass; fail-closed on secret-in-evidence and
  raw-in-table; guard-map fail-closed on absent tables; migrated guard-map declares the `=0` guards.
- Evidence: `no-writeback-no-raw-financial-output-proof.json` / `.md`.
