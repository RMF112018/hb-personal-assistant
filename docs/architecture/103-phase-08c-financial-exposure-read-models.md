# Phase 08C Prompt 06: Financial Exposure Read Models (advisory marts)

## Scope (from manifest)
Build advisory exposure marts for Phase 08C.

Required:
1. Local read models for pending exposure, approved exposure, budget changes, commitments, purchase orders, subcontractor invoices, change events, RFQs, owner contracts, direct costs (where available), and review-required items.
2. Use normalized amounts only where allowed (via V35 normalized facts / P03 layer; TEXT canonical, no float).
3. Distinguish deterministic relationships (action signals, budget changes, known procore links) from candidate relationships (ambiguous/cross-source).
4. Include confidence_label, review_tier, source_references, advisory_status.
5. Generate `exposure-mart-preview.json` (in 08C evidence dir).

Stop if any output is presented as a final exposure determination, claim, entitlement, or forecast.

Guardrails (enforced): local-first/read-only, no raw payloads in evidence, Decimal/strings for money, advisory only, dry-run posture for commands.

Base: post V34 + V35 (second_brain_financial_exposure_summary_items table with full guard CHECKs for advisory_only=1, no-raw, no-determination etc.). Contract: phase_08c_exposure_summary_contract.json (exposure_categories + required_fields).

## Approach
- Core builder in `construction/second_brain/financial_completeness.py` (following P03/P04/P05 patterns for currency/wbs/coverage).
- Reuses:
  - `load_phase_08c_contract("exposure_summary_contract")` for categories/fields.
  - `procore_cost_exposure.build_cost_exposure` + schedule equivalent (for deterministic items from action signals + budget changes; amounts as strings).
  - V35 normalized amount facts for `normalized_amount_ref` (TEXT).
  - Direct INSERT to `second_brain_financial_exposure_summary_items` for snapshots (with all guard columns).
- Items always carry: the 7 contract required_fields + `relationship_kind` ("deterministic" | "candidate") + `advisory_status` ("advisory review aid only — not a final exposure determination...").
- Preview JSON: written as side-effect (or explicit); top-level guardrails, summary (by_category, det/cand counts, review count), items list, notes attesting "advisory only", "normalized only", "source preserved", stop checks (no raw, no det language).
- CLI `second-brain financial exposure-summary --json` now calls the builder and surfaces `exposure_mart_preview_path` + `summary`.
- Gate `exposure_marts` (in 08c data-quality gates) now calls builder and asserts advisory language + no determination claim (pass/warning).
- No live calls, no writeback, no float, no raw in output/evidence.

## Key Artifacts
- New/updated: `financial_completeness.py` (builders + preview writer + snapshot).
- `data_quality.py` (real exposure_marts gate).
- `cli/second_brain.py` (wire in exposure-summary for preview_path).
- Test extension in `test_phase_08c_financial_completeness.py` (seeds facts, asserts fields/relationship_kind/normalized str/advisory/no-det, json written, CLI).
- Generated: `docs/evidence/.../exposure-mart-preview.json` (11+ items, structure per contract, 0 raw, advisory attest).
- Arch: this file + entry in `00-README.md`.

## Verification (executed)
- ruff check/format + mypy on touched (surgical fixes for any new F/SIM).
- pytest test_phase_08c... -k exposure (new test passes; pre-existing unrelated P04 tolerated).
- All 08C CLIs per validation_matrix: construction-agent validate, second-brain financial readiness/coverage/exposure-summary/review-items, data-quality phase-08c-gates + no-writeback-proof (all ok=true or expected warning for empty data; exposure-summary now includes preview_path + summary; gates has exposure_marts with total + advisory check).
- Python attest on preview: has items, required fields, relationship_kind, normalized_amount_ref is str/null, advisory_status contains "advisory review aid only" + "not a final...", summary has det/cand, no raw keys/values in json, no "final exposure determination" as claim.
- git staged only the required paths for this prompt (financial_completeness.py, data_quality.py, cli/second_brain.py, test_..., exposure-mart-preview.json, 103-*.md, 00-README.md).
- No stop violations (no raw, no determinations, money strings, advisory language everywhere).

## Commit
Traditional per manifest (title includes 00_PACKAGE_MANIFEST.md + version + "Prompt 06: Financial Exposure Read Models"). Staged only required. 08C not closed. All financial outputs advisory review aids only.

See session evidence + the generated preview json for full attestation.
