# Phase 07C — Prompt 02: Document Schema and Card Contracts Proof

**Phase:** Construction Intelligence 07C — Document Intelligence Promotion
**Prompt:** 02 — Document Schema and Card Contracts
**Generated (UTC):** 2026-05-31
**Baseline:** validations ran against working tree at parent commit
`dd92ad41e63af24bf27c7ef8f611020d3cc8174f`; schema version **24** (V24 applied this prompt); package
**1.3.0**. Landing commit is the child of that parent.

> Leak-safe: table/column **names**, enum identifiers, counts, command names, and exit codes only. No raw
> document text, file names, web URLs, parent paths, signed/download/tokenized URLs, tokens, secrets, PEMs,
> raw email bodies, calendar payloads, prompts, responses, tenant GUIDs, or UPNs.

## 1. What changed (additive only)

- **Migration V24** (`store/migrator.py`, `LATEST_SCHEMA_VERSION` 23→24): extends the existing empty V5
  `construction_document_cards` via idempotent `ALTER ADD COLUMN` (25 new columns incl. canonical
  `document_card_id` + `UNIQUE INDEX`, hashed/redacted identity fields, review/extraction/confidence state,
  and six `*_persisted=0` CHECK guards) and creates 5 satellite tables + 5 indexes. Legacy `card_id` PK
  retained untouched. V1–V23 unchanged.
- **5 contracts** installed under `resources/json/` (`document_card_contract`,
  `document_classification_contract`, `document_project_match_contract`,
  `document_relationship_candidate_contract`, `controlled_extraction_contract`; all `phase07c-v1`).
- **`construction/document/`** new package with `load_document_contract` / `load_all_document_contracts`.
- **Lifecycle contract** `table_lifecycle_status_contract.json`: +5 satellites, `table_count` 105→110.

New tables (V24): `construction_document_classification_candidates`,
`construction_document_project_match_candidates`, `construction_document_relationship_candidates`,
`construction_document_intelligence_previews`, `construction_document_projection_runs`.

## 2. Validation matrix

| Command | Exit | Result |
|---|---:|---|
| `python -m compileall src tests` | 0 | clean |
| `ruff check .` | 0 | `All checks passed!` |
| `mypy src` | 0 | `Success: no issues found in 166 source files` |
| focused: `pytest test_phase_07c_schema_v24.py test_document_contracts.py test_phase_07b_schema_v23.py` | 0 | 30 passed |
| `pytest -m "not live and not integration and not manual"` | 0 | `2011 passed, 1 deselected` (+24 vs Prompt 01) |
| `construction-agent data-quality table-inventory --json` | 0 | `schema_version=24`; `contract_table_count=110`; `live_table_count=106`; `in_db_not_in_contract=[]` |
| `construction-agent data-quality no-writeback-proof --json` | 0 | `proof_passed=true`; `schema_version=24` (new empty V24 tables not yet scanned — deferred to Prompt 12) |
| `construction-agent data-quality gates --json` | 0 | `schema_version=24`; `document_card_population_status=deferred_not_blocking` (future_phase 07C); meeting_prep/risk_digest `blocked` |
| `construction-agent validate` / `procore validate` / `graph files status` / `graph files no-writeback-proof` / `graph calendar status` / `graph mail status` (all `--json`) | 0 | green |

## 3. Schema guard verification

A direct fresh-DB check confirmed: V24 applies to 24 and is idempotent (one `schema_migrations` v24 row on
double-apply); the 5 satellites + 25 new card columns + `ux_document_cards_document_card_id` exist; and
every `*_persisted=0` CHECK rejects a non-zero insert (card layer and satellite layer both fail closed with
`IntegrityError`). No raw-text / signed-URL / download-URL / payload column exists — only hashed/redacted/
bounded fields plus the guard flags.

## 4. Readiness (not overstated)

Document cards remain **0 rows** (no materialization in this prompt) → `document_card_population_status`
stays `deferred_not_blocking` / future_phase 07C; `meeting_prep_readiness_claim` and
`risk_digest_readiness_claim` remain `blocked`. No gate or closeout overstates readiness.

## 5. Leak scan

Installed contracts, the new package, the architecture doc, and this evidence were scanned: contracts are
enum/identifier metadata only (a test asserts no `https://` / email / secret patterns); no raw values,
URLs, tokens, secrets, GUIDs, or UPNs anywhere.

## 6. Outcome

Additive V24 schema + 5 contracts + loader landed; full matrix green at schema 24; no stop condition
triggered; no readiness overstated. **07C is cleared to proceed to Prompt 03 (Source Indexing Readiness
and Scope Compliance)** and Prompt 04 (Document Card Materialization), which will populate
`construction_document_cards` (setting `card_id = document_card_id`) from the file-intelligence layer using
hashed/redacted derivatives per the installed contracts.
