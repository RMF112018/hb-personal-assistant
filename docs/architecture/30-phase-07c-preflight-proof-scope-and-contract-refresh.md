# 30 — Phase 07C Preflight: No-Raw Proof Scope Disclosure + Lifecycle Contract Refresh

**Phase:** 07C (Document Intelligence Promotion) — Prompt 01 (07B Remediation Preflight)
**Status:** Implemented at this record's commit.
**Evidence:** `docs/evidence/construction-intelligence-phase-07c-document-intelligence/01-phase-07b-gap-audit.md` (§Prompt 01).

Before any 07C document-card work, the preflight hardens two **truthfulness** boundaries so document
intelligence cannot inherit a false safety assumption. Both changes are strictly additive — no schema,
CLI, or gate change; the no-writeback proof stays green; gates are unchanged (verified honest).

## 1. No-raw-persistence proof — explicit scope disclosure

`build_data_quality_no_writeback_proof()` (`construction/data_quality/safety.py`) emits a generically
named `no_raw_values_persisted` flag whose true scope (per doc 29) is the 07A data-quality + 07B
calendar/email/thread/candidate surfaces. It does **not** scan the Phase 06A file-intelligence layer
`construction_drive_item_inventory`, which stores raw drive-item metadata (`name`, `web_url`,
`parent_path`) by design. 07C promotes document cards from exactly that layer, so the undisclosed
exclusion was a latent contamination risk.

The fix is **disclosure, not scanning** — scanning the table would be wrong, because its `web_url`
legitimately holds `https://` and would flip a correct proof to failed. The proof now additionally
returns:

- `no_raw_values_persisted_scope` — a string naming the exact surfaces the flag covers.
- `raw_staging_layers_out_of_scope` — a list (constant `_RAW_STAGING_LAYERS_OUT_OF_SCOPE`) naming
  `construction_drive_item_inventory`, its raw columns (identifiers only — never values), its origin
  phase (`06A`), and the required handling: hash/redact before any 07C document-card, evidence, or
  Obsidian output.
- The `note` is tightened to state the exclusion inline.

`proof_passed` logic and the six `*_07b` checks are unchanged. A focused test
(`test_safety_proof_discloses_raw_staging_layer_out_of_scope`) asserts the disclosure is present, names
the layer, and is itself identifier-only (no URLs/emails/secrets via the shared secret scanner).

## 2. Lifecycle contract refresh — map the V20/V21 07A tables

The canonical `resources/json/table_lifecycle_status_contract.json` (see remediation-07b doc §2) was
seeded from the **pre-V20** 07A manual inventory, so nine V20/V21 Phase 07A data-quality / relationship
tables were never mapped and surfaced as `unknown_requires_audit` / `in_db_not_in_contract`:
`construction_data_quality_runs`, `data_quality_gate_results`, `construction_table_lifecycle_registry`,
`source_system_record_map`, `relationship_resolution_queue`, `project_source_coverage_mart`,
`source_record_summary_mart`, `relationship_quality_mart`, `cross_domain_context_readiness_mart`.

They are added additively under a `data_quality_v20v21` family (`phase_owner="07A"`,
`blocking_for_phase="none"`; `data_quality_gate_results` → `operational_populated`, the other eight →
`operational_empty_expected`/`empty`). `table_count` 96 → 105. The four `procore_sync_*` entries that
are `in_contract_not_in_db` are **left intact** — they are real schema tables simply not materialized in
the local store, not contract errors.

After the refresh: `contract_table_count=105`, `in_db_not_in_contract=[]`, no live table left
`unknown_requires_audit`; `in_contract_not_in_db` correctly remains the four `procore_sync_*`. A focused
test (`test_v20_v21_data_quality_tables_are_mapped_not_unmapped`) pins this.

## Guardrails

Read-only/offline posture preserved; no external writeback; no mutation endpoints or write scopes. No
raw document text, email body, calendar payload, prompt, or response persisted. The disclosure and
contract entries carry only table/column **names** and lifecycle metadata — never raw values, URLs,
tokens, secrets, or PEMs. Gates and readiness claims are unchanged (meeting-prep / risk-digest remain
`blocked`; 07C still `blocked_by document_card_population_status`). No 07D readiness claimed.
