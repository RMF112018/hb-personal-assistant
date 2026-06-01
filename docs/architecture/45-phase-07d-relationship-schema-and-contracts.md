# 45 — Phase 07D Relationship Schema and Contracts (V25)

**Status:** Implemented (Phase 07D Prompt 02). Additive; schema `V24 → V25`.
**Scope:** the data substrate for cross-source relationships and meeting prep — schema,
machine-readable contracts, policy seeds, and a loader. No builders, CLI commands, or gate
wiring (those are Prompts 03–14).

## Why

Phase 07D turns the per-source intelligence built in 07A–07C (document, email, calendar,
Procore candidates) into **cross-source** relationships, evidence trails, meeting-prep briefs,
issue history, a risk digest, and aging/exposure reports. Every later 07D prompt reads from a
shared set of tables and contracts that did not exist. This record documents that substrate,
laid down first per the package "Backfill order" (create schema/contracts before any
normalization or materialization). The tables ship **empty** by design.

## The ten V25 tables

All under `SQLiteMigrator.V25_STATEMENTS` (`src/hb_assistant/store/migrator.py`), created with
`CREATE TABLE IF NOT EXISTS` and applied in an idempotent, version-guarded block.

- **Relationships:** `cross_source_relationship_candidates` (advisory edges, `review_required`
  default 1) and `cross_source_relationships` (promoted/confirmed edges). Both keyed for dedup
  by `UNIQUE(source_family, source_record_ref, target_family, target_record_ref,
  relationship_type)`.
- **Evidence:** `source_evidence_trails` — redacted `source_refs_json` + `confidence_class`
  + `stale_unknown_flags_json`, referenced by candidates, brief sections, and the digest/issue
  tables via `evidence_trail_id`.
- **Meeting prep:** `meeting_prep_brief_runs` (run ledger, `mode IN ('dry_run','apply')`) and
  `meeting_prep_brief_sections` (redacted sections, FK → runs `ON DELETE CASCADE`).
- **Digests/reports:** `project_issue_history_items`, `project_risk_digest_items`
  (`risk_source_class` CHECK), `aging_exposure_report_items`
  (`UNIQUE(project_key, record_family, record_ref)`).
- **Run ledgers:** `cross_source_intelligence_obsidian_runs` (Obsidian projection runs) and
  `phase_07d_validation_runs` (07D validation runs).

## Invariants

1. **No-raw / no-writeback guard columns.** Every table carries all eight guards
   (`raw_email_body_persisted`, `raw_document_text_persisted`, `raw_calendar_payload_persisted`,
   `raw_prompt_persisted`, `raw_response_persisted`, `signed_url_persisted`,
   `download_url_persisted`, `external_writeback_performed`), each
   `INTEGER NOT NULL DEFAULT 0 CHECK(... = 0)`. SQLite rejects any attempt to record raw
   content, a signed/download URL, or an external writeback — the same four-layer posture used
   for V24 document tables, extended with the email/calendar/prompt/response guards.
2. **Deterministic idempotency.** Candidate/relationship IDs are deterministic hashes (writer
   responsibility, Prompt 03+); the UNIQUE edge keys make re-runs upsert-by-edge rather than
   duplicate. `apply()` is idempotent (single `schema_migrations` row for V25).
3. **No auto-promotion.** Candidates default `review_required = 1`. The relationship contract
   (`no_auto_promotion_for`) and `cross_source_relationship_policy.seed.yaml` block local
   promotion of `weak_heuristic` / `model_proposed` / `sensitive_high_impact`; only
   `deterministic` may be locally promoted, and only when no sensitive/high-impact flag is set.
4. **Advisory only.** Outputs are project-intelligence aids; the meeting-prep brief policy
   forbids final legal/contractual/claim/safety/financial determinations.

## Contracts and policy seeds

- **JSON contracts** (`src/hb_assistant/resources/json/`, importlib-loaded): one per domain —
  `cross_source_relationship_contract`, `source_evidence_trail_contract`,
  `meeting_prep_brief_contract`, `project_issue_history_contract`, `risk_digest_contract`,
  `aging_exposure_report_contract` — plus `phase_07d_data_quality_gates` and
  `phase_07d_validation_matrix` staged for Prompts 12/14.
- **Policy seeds** (`resources/config/*.seed.yaml`, repo-root-resolved): relationship promotion
  policy, review-required relationship rules, meeting-prep brief policy, risk-digest policy,
  aging/exposure thresholds. The OneDrive selected-folder allowlist already lives in the
  Prompt 01 document-source policy and is not duplicated here.
- **Loader** (`construction/relationships/contracts.py`): mirrors `document/contracts.py`
  (JSON: importlib → filesystem → `{}`) and `config/loader.py` (seeds: repo-root path). Pure,
  read-only, identifier/enum only.

## Table-inventory reconciliation

The ten tables are registered in `table_lifecycle_status_contract.json`
(`table_family: cross_source_07d`, `phase_owner: 07D`, `operational_empty_expected`,
`v: V25`); `table_count` `110 → 120`. `data-quality table-inventory` therefore classifies them
from the contract (no unmapped/unknown rows), matching how V20/V21/V24 tables were registered.

## Related records

- `30–42` — Phase 07C document intelligence (the per-source candidate layer 07D consumes).
- `43` — 07D source-scope all-folders + review-routing remediation (Prompt 01).
- `44` — high-fidelity local PDF extraction (Prompt 01A).
