# 100 — Phase 08C Decimal Amount Normalization (Prompt 03)

**Baseline**: Post-P02 inventory at `06241a7` (V35, 161 tables, 32 eps/25 tables audited, inventory JSONs present, 08c gates pass on contract/presence).

**Objective** (per prompt): Implement decimal-safe amount parsing/read-model classification.
- Add Decimal-only helpers + tests that prohibit float-based money normalization.
- Discover amount fields from the P02 inventory output.
- Classify each as parseable / rejected / missing / ambiguous / stale / conflicting / review-required (per amount_normalization_contract).
- Store canonical decimal strings, source references, value hashes, rejection reasons, advisory labels in V35 substrate.
- Preserve source amount strings in existing procore_financial_* tables (no duplication of raw payloads).
- Generate `amount-normalization-proof.json` and `amount-normalization-rejected-values.json`.

**Stop if float(), SQLite REAL, or JSON number coercion used for money decisions** (enforced in helpers + tests + proof attest + grep).

## Changes
- `src/hb_assistant/procore/normalizers/financial.py`: import Decimal/InvalidOperation; updated module doc + parse_amount (now raises on float with explicit "prohibited" message; only str/int/Decimal for money); added to_canonical_decimal_text, compute_minor_units, source_value_hash, classify_amount (returns the 7 statuses + canonical/minor/hash/reason/tier/advisory; uses Decimal(str(v)) only; loads policy for review_tier on ambiguous/rejected).
- `tests/test_procore_normalizers_financial_amounts.py` (new): 13 tests for prohibition (float raises in parse/to_canonical/classify), Decimal safety (0.1+0.2 -> "0.3"), all 7 statuses, hash stable, policy review, static "no float( in money helpers".
- `src/hb_assistant/construction/second_brain/financial_amount_normalization.py` (new): discover_amount_fields_from_inventory (loads P02 JSON or fallback list of (table, field)); run_amount_normalization (reads source TEXT via amount_facts + fallback, classify, best-effort INSERT to fact_normalization_runs + amount_facts_normalized with full refs + canonical + guards + advisory); build_amount_normalization_proof (computes classifications on samples from inventory fields, writes the two JSONs with stats/contract/money_storage/no_float/source_preserved/advisory).
- `src/hb_assistant/construction/second_brain/data_quality.py`: minimal wire in 08c amount_normalization gate to include dry-run norm stats (real counts when exercised).
- Generated: amount-normalization-proof.json (run, stats e.g. parseable 10 / rejected 1 / missing 1 from samples, contract, no_float_in_path:true, source_preserved_note, guardrails, advisory), amount-normalization-rejected-values.json (the rejected cases with hash/reason).
- `docs/architecture/100-...md` (this) + surgical in 00-README.md.

Source amounts (e.g. "10200000.50", "N/A") stay in procore_financial_* (TEXT); 08C normalized has only canonical + hash + ref + status + reason (no raw payloads).

All money paths: Decimal only; float prohibited at boundary (tests + helpers + proof attest + post-edit grep).

## Verification
- pytest tests/test_procore_normalizers_financial_amounts.py : 13/13 pass (prohibition, Decimal safety, statuses).
- 08c-gates (amount now includes norm stats from dry run).
- Sensitive scan on JSONs: 0 bad.
- No float() for money in edited sources (grep).
- Proofs self-contained with "Decimal-only", "source preserved", "7 statuses", "no float/REAL".
- Stops clear; 08C not closed.

Staged only required (src edits + new test + new module + 2 JSONs + arch 100- + 00-README). 

Package manifest for title/version + contract/policy shapes only; repo truth authoritative.