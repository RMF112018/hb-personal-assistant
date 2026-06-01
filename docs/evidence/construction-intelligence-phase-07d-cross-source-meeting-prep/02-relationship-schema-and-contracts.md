# Phase 07D · Prompt 02 — Relationship Schema and Contracts

**Generated (UTC):** 2026-06-01
**Validation HEAD (pre-commit):** `9e91b834174cf488ca46bf81c8d6d95e7a9807d0` (Prompt 01 closeout / live-smoke)
**Package version:** `1.3.0` · **Schema version:** `24` → **`25`** (additive migration V25)
**Verdict:** The 07D cross-source substrate (schema + contracts) is laid down. Ten additive
V25 tables ship **empty**, eight JSON contracts and five policy seeds are installed and load
cleanly, the table-inventory reconciles at **120** contract tables with all ten new tables
mapped from contract (none unmapped). Both no-writeback proofs stay `ok/proof_passed=true`.
**Prompt 03 (cross-source relationship substrate) may proceed.**

This prompt is additive and read-only. It adds **schema + contract data + a loader + tests
only** — no builders, no new CLI commands, no gate wiring, no external writeback. All ten
tables carry the eight no-raw / no-writeback guard columns enforced by `CHECK(... = 0)`.

---

## 1. Repo-truth preflight

| Item | Value |
| --- | --- |
| `git rev-parse HEAD` | `9e91b834174cf488ca46bf81c8d6d95e7a9807d0` |
| `git status --short` | clean (only untracked `.claude/`) at start |
| `python --version` | `Python 3.12.11` (toolchain `.venv/bin/python3.12`) |
| `hb-assistant --version` | `hb-assistant 1.3.0` |
| Schema version (pre) | `24` (`LATEST_SCHEMA_VERSION`) |
| Package version | `1.3.0` (`pyproject.toml`) |

**Ancestry (all confirmed ancestors of HEAD):** 07A `3cf1652bf55303ceea25b2bbc6b5b1785111a335`
→ 07B `748ed7e6519ada0a74d09376f2d2fe353627ac2b` → 07C `733ffedae071ce6a766a33fcd9233205364b8013`.
No branch or worktree created.

**07D evidence folder (pre):** `00-repo-truth-rebaseline.md`, `01-07c-remediation-preflight.md`.

---

## 2. What changed (additive only)

### 2.1 Schema — V25 (`src/hb_assistant/store/migrator.py`)
`LATEST_SCHEMA_VERSION` `24 → 25`; new `V25_STATEMENTS` (ten `CREATE TABLE IF NOT EXISTS`
+ supporting indexes) and an idempotent apply() block
(`v25_cross_source_relationship_meeting_prep_schema`). V1–V24 untouched. Ten tables, all
shipping empty:

| Table | Idempotency key | Notes |
| --- | --- | --- |
| `cross_source_relationship_candidates` | `UNIQUE(source_family, source_record_ref, target_family, target_record_ref, relationship_type)` | `confidence_class`/`promotion_status` domain CHECKs; `review_required` default 1 |
| `cross_source_relationships` | same UNIQUE edge key | promoted/confirmed edges; `promotion_status`/`promoted_by` CHECKs |
| `source_evidence_trails` | PK `evidence_trail_id` | redacted `source_refs_json` |
| `meeting_prep_brief_runs` | PK `brief_run_id` | `mode IN ('dry_run','apply')` |
| `meeting_prep_brief_sections` | PK `section_id` | FK → brief_runs ON DELETE CASCADE; `section_redacted` |
| `project_issue_history_items` | PK `issue_family_id` | `source_families_json` |
| `project_risk_digest_items` | PK `risk_digest_id` | `risk_source_class` CHECK; `summary_redacted` |
| `aging_exposure_report_items` | `UNIQUE(project_key, record_family, record_ref)` | `threshold_band`, `stale_flag` |
| `cross_source_intelligence_obsidian_runs` | PK `obsidian_run_id` | `mode` CHECK |
| `phase_07d_validation_runs` | PK `validation_run_id` | `mode` CHECK |

**Guard-column invariant (every table):**
`raw_email_body_persisted`, `raw_document_text_persisted`, `raw_calendar_payload_persisted`,
`raw_prompt_persisted`, `raw_response_persisted`, `signed_url_persisted`,
`download_url_persisted`, `external_writeback_performed` — each
`INTEGER NOT NULL DEFAULT 0 CHECK(... = 0)`.

### 2.2 Contracts — 8 JSON (`src/hb_assistant/resources/json/`)
`cross_source_relationship_contract`, `source_evidence_trail_contract`,
`meeting_prep_brief_contract`, `project_issue_history_contract`, `risk_digest_contract`,
`aging_exposure_report_contract`, `phase_07d_data_quality_gates`,
`phase_07d_validation_matrix`. The relationship contract pins
`no_auto_promotion_for: [weak_heuristic, model_proposed, sensitive_high_impact]`. The latter
two files are forward-declaration data for Prompts 12/14 (no code wiring this prompt).

### 2.3 Seeds — 5 YAML (`resources/config/*.seed.yaml`)
`cross_source_relationship_policy`, `review_required_relationship_rules`,
`meeting_prep_brief_policy`, `risk_digest_policy`, `aging_exposure_thresholds`. The package's
`onedrive_selected_folder_allowlist_policy.seed.yaml` was **intentionally excluded** — that
policy already landed in Prompt 01 (`document_source_policy.seed.yaml` + `source_scope.py`);
re-adding it would duplicate/drift.

### 2.4 Loader — `src/hb_assistant/construction/relationships/contracts.py`
Mirrors `construction/document/contracts.py` (importlib → filesystem → `{}` fallback) for
JSON contracts and `construction/config/loader.py` (repo-root resolution) for seeds. Read-only,
identifier/enum metadata only.

### 2.5 Table inventory registration
`table_lifecycle_status_contract.json`: added the ten V25 tables (`table_family:
cross_source_07d`, `phase_owner: 07D`, `operational_empty_expected`, `v: V25`); `table_count`
`110 → 120`. `tests/test_data_quality_table_inventory.py` assertion `110 → 120`.

---

## 3. Validation commands (all exit 0)

| Command | Exit | Key result |
| --- | --- | --- |
| `python -m compileall src tests` | 0 | clean |
| `ruff check .` | 0 | All checks passed |
| `mypy src` | 0 | no issues in **177** source files |
| `pytest -m "not live and not integration and not manual"` | 0 | **2135 passed**, 1 deselected |
| `construction-agent validate --json` | 0 | 4/4, schema **V25** |
| `procore validate --json` | 0 | pass |
| `graph files status --json` | 0 | pass |
| `graph files no-writeback-proof --json` | 0 | `ok=true` |
| `graph calendar status --json` | 0 | pass |
| `graph mail status --json` | 0 | pass |
| `construction-agent data-quality gates --json` | 0 | `meeting_prep_readiness.ready=true`, `auto_readiness_allowed=false` |
| `construction-agent data-quality no-writeback-proof --json` | 0 | `proof_passed=true`, schema 25 |
| `construction-agent data-quality table-inventory --json` | 0 | schema_version **25**, contract_table_count **120**, ten 07D tables `source=contract`, `in_db_not_in_contract` ∩ 07D = `[]` |

New targeted tests: `tests/test_phase_07d_schema_v25.py` (tables present + empty; eight guard
CHECKs declared per table; valid-row guard rejection; domain CHECKs; `review_required` default 1;
UNIQUE edge dedup; idempotent re-apply; V1–V24 intact) and `tests/test_phase_07d_contracts.py`
(all 8 contracts + 5 seeds load; version/required-key presence; weak/model/sensitive
no-auto-promotion; sensitive-category review rules; identifier-only leak scan). `pytest`
delta `2080 → 2135`.

One pre-existing assertion was updated: `tests/test_phase_07c_schema_v24.py` hard-coded
`LATEST_SCHEMA_VERSION == 24`; V24 is additive and no longer the latest, so the assertion now
reads `== LATEST_SCHEMA_VERSION >= 24` (V24 document schema presence is still verified
downstream in the same test).

---

## 4. SQLite truth (live DB, schema V25 after CLI run)

Running `data-quality table-inventory` migrated the live local DB additively to V25. All ten
07D tables exist and are **empty** (0 rows); they are classified from the lifecycle contract
(`source=contract`, `operational_empty_expected`), not left unmapped. `live_table_count=116`,
`contract_table_count=120` (four contract tables remain not-yet-materialized in this DB — a
pre-existing condition unrelated to 07D).

---

## 5. Guardrails honored

- **No external writeback / no write scopes.** Schema/contract/loader/test changes only; no
  Microsoft 365 / SharePoint / OneDrive / Outlook / Calendar / Procore mutation. Both
  no-writeback proofs pass post-change.
- **No raw content / URLs / tokens.** Every table enforces the eight `CHECK(... = 0)` guards;
  contracts and seeds are identifier/enum metadata only (leak-scan tests pass).
- **No auto-promotion.** `cross_source_relationship_candidates.review_required` defaults to 1;
  the relationship contract + policy seed block local promotion of weak/model/sensitive
  /high-impact relationships.
- **Readiness not overstated.** Tables ship empty; `meeting_prep_readiness.ready` reflects the
  Prompt 01 gate state and `auto_readiness_allowed=false` — Prompt 02 makes no readiness claim
  beyond "substrate exists."

---

## 6. Handoff

**Prompt 03 (cross-source relationship substrate) is allowed to proceed.** The V25 tables,
contracts, policy seeds, and loader are in place. Prompt 03+ will normalize existing
document/email/calendar/Procore candidates into `cross_source_relationship_candidates`, build
`source_evidence_trails`, and (Prompts 06–11) populate the meeting-prep / issue-history /
risk / aging / Obsidian tables. The `phase_07d_data_quality_gates` and
`phase_07d_validation_matrix` contracts are staged for Prompts 12/14 to wire into `gates.py`
and the validation command set.
