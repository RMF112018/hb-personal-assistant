# Phase 07A Gap Audit & 07B Blocker Inventory — Prompt 00

**Date:** 2026-05-31
**Phase:** 07B — Calendar & Email Thread Intelligence Foundation
**Prompt:** 00 — Repo Truth Audit And 07A Gap Inventory
**Run UTC:** 2026-05-31T10:33:13Z
**Baseline:** HEAD `3cf1652…` (`main`), version `1.3.0`, schema **V21**

This file verifies Phase 07A closeout claims against current repo truth and classifies every
07A/07B blocker. Raw command evidence and exit codes are in
[`00-repo-truth-rebaseline.md`](./00-repo-truth-rebaseline.md). 07A's own closeout/handoff bundle
lives at `docs/evidence/construction-intelligence-phase-07a-data-quality/`.

---

## 1. 07A closeout-claim verification (claims vs repo truth)

| 07A closeout claim | Repo-truth verdict | Evidence / citation |
|---|---|---|
| Schema at V21 (`v21_agent_ready_query_marts`) | **Confirmed** | `migrator.py` applies version 21; `construction-agent validate` → `schema_version=21` |
| `ruff check .` exits 1 (~24 pre-existing issues) | **Confirmed (24)** | exit 1; `ruff --statistics`: 17 SIM105 / 3 F401 / 1 B007 / 1 B011 / 1 F841 / 1 I001 |
| Safe `pytest` subset exits 1 (known baseline, no regressions) | **Confirmed** | exit 1; 31 failed / 1883 collected; failures classified below as version-pin + known 07B gap + weekend-date |
| `mypy src` exits 0 | **Confirmed** | `Success: no issues found in 152 source files` |
| `construction-agent validate --json` exits 0 | **Confirmed** | exit 0; schema + registry + review rules + model routing all ok |
| `procore validate --json` exits 0 | **Confirmed** | exit 0; 28/28 checks |
| `graph files status --json` exits 0 | **Confirmed** | exit 0; ok=true (delegated, offline posture) |
| `data-quality no-writeback-proof` exits 3 (5 V21 marts lack CHECK; not a leak) | **Confirmed** | exit 3; only `sqlite_raw_body_guardrail…` check fails; code/import/secret scans pass |
| `data-quality table-inventory --json` not implemented | **Confirmed** | exit 2 `No such command 'table-inventory'` |
| No operational `graph calendar status --json` | **Confirmed** | exit 2 `No such command 'calendar'` |
| `email_classifier_persistence_status` deferred → 07B | **Confirmed** | gate `deferred_not_blocking`, future_phase=07B; `upsert_email_model_classification` undefined (see §2) |
| `calendar_population_status` deferred → 07B | **Confirmed** | gate `deferred_not_blocking`, future_phase=07B; `calendar_events` table empty (0 rows) |
| `email_thread_summaries` present but unpopulated | **Confirmed** | table at `migrator.py:1656`; `SELECT COUNT(*)` = 0 |
| Relationship quality ready for 07D | **Confirmed** | deterministic/candidate orphan gates both `pass`; `07D.relationship_quality_ready=true` |
| 07D meeting-prep / risk-digest / financial NOT ready | **Confirmed** | `07A_exit.ready=false`; `08B.financial_readiness="blocked"`; no readiness claim present |

**No 07A closeout claim was found to be stale or overstated.** All claims reproduce against current
`main`. 07A closed honestly with a documented non-green baseline.

---

## 2. Blocker inventory (classified)

### 2A. 07A-residual — carried into Prompt 01 (preflight quarantine / remediation)

| # | Blocker | Severity | Owning prompt | Current status & citation |
|---|---|---|---|---|
| R1 | `ruff check .` exits 1 — 24 issues on 07A data-quality surfaces (`data_quality/marts.py`, `safety.py`, `__init__.py` + their tests) | Medium | **07B P01** | exit 1; 17 SIM105 are mechanically fixable (`contextlib.suppress`); 4 auto-fixable |
| R2 | Safe `pytest` subset exits 1 — 20 migration version-pin assertions (`assert apply() == 19/20`, migrator now returns 21) | Medium | **07B P01** | failing files: `test_data_quality_schema_v20` (3), `test_procore_history_migration_v7` (3), `test_procore_financials_v8` (3), `test_procore_financials_v9` (3), `test_email_registry_migration_v10` (2), `test_email_operational_schema_v11` (2), `test_email_model_classifications_schema_v14` (2), `test_email_body_vault` (1), `test_construction_store_repositories::test_v5_migration_is_idempotent` (1). Stale expectations — not regressions |
| R3 | 4 `test_automation.py` failures are date-dependent (2026-05-31 = Sunday → `skipped_weekend_manual_only`) | Low | **07B P01** (document; environmental) | not a code defect; passes on weekdays |
| R4 | `data-quality no-writeback-proof` exits 3 — 5 V21 mart tables lack `CHECK(raw_body_persisted = 0)` | Medium | **07B P01 / P02** (additive CHECK via new migration) or documented defensive-DDL note | code/import/secret scans clean; documented as defensive-DDL gap, **not** a raw-body leak |
| R5 | `data-quality table-inventory --json` not implemented (referenced by validation matrix) | Low | **07B** (implement or de-reference) | exit 2 `No such command`; 07A used a manual inventory instead |

### 2B. 07B-net-new — net Phase 07B implementation scope

| # | Blocker | Severity | Owning prompt | Current status & citation |
|---|---|---|---|---|
| B1 | No `graph calendar status --json` / read-only calendar endpoint guard | High | **07B P03** | exit 2 `No such command 'calendar'`; `cli/graph.py` exposes only `files`/`mail` |
| B2 | Calendar source registry / crawl receipts / project-match fields / review routing absent; `calendar_events` (V1, legacy) empty | High | **07B P02 + P04 + P05** | `calendar_events` at `migrator.py:65`; `SELECT COUNT(*)` = 0; `graph/calendar_client.py` exists but no 07B ingestion path |
| B3 | `upsert_email_model_classification` repository method missing → email classifier cannot persist | High | **07B P06** | `email_classifier.py` **calls** it; **no `def`** in `src/`; runtime `AttributeError` on `ConstructionStore` (`construction/store/repositories.py`); 7 `test_email_classifier.py` failures |
| B4 | `email_thread_summaries` present but unpopulated (review-controlled, redacted) | High | **07B P07** | table at `migrator.py:1656`; `SELECT COUNT(*)` = 0 |
| B5 | Meeting ↔ email-thread relationship candidates do not exist | Medium | **07B P08–P09** | no candidate table/path; depends on B1–B4 |
| B6 | Calendar/email Obsidian outputs (marker-bounded, no raw content) not built | Medium | **07B P10** | follows 07A Prompt-06 register pattern |
| B7 | 07B data-quality gates + no-writeback/no-secret/no-raw-body proof must turn green | High | **07B P11–P12** | calendar + email classifier gates currently `deferred_not_blocking`; must move to `pass` |

### 2C. Deferred (documented, NOT in 07B scope)

| # | Item | Owning phase | Citation |
|---|---|---|---|
| D1 | `document_card_population_status` / document cards / file-to-record links | **07C** | gate `deferred_not_blocking`, future_phase=07C |
| D2 | `financial_amount_parseability` + `financial_currency_completeness` | **08B** | gates `warning`, future_phase=08B; `08B.financial_readiness="blocked"` |
| D3 | Meeting-prep MVP / risk digest / cross-source promotion workflow | **07D** | only after 07B+07C+relationship+safety gates pass |

---

## 3. Stop-condition check (this prompt)

- No mutation/writeback was required or performed. ✅
- No raw/private value appears in evidence (auth UPN/tenant/cache paths redacted to structural
  facts). ✅
- No validation failure was hidden — all 31 test failures and both non-green exit codes (ruff=1,
  pytest=1, no-writeback-proof=3) are recorded and classified. ✅
- Every guardrail provable from read-only command output. ✅
- No Phase 07D readiness claimed — 07D remains explicitly blocked. ✅

---

## 4. Go / No-Go for Prompt 01

**GO — Prompt 01 (07A Remediation Preflight) may proceed.**

Rationale:
- Every 07A closeout claim is confirmed against repo truth; nothing is stale or overstated.
- All non-green signals are explained and classified: 07A-residual items (R1–R5) are exactly the
  quarantine/remediation targets Prompt 01 owns; 07B-net-new items (B1–B7) are expected unbuilt
  scope, not defects; deferred items (D1–D3) belong to 07C/07D/08B.
- No blocker requires external-system mutation, raw-body persistence, or any guardrail violation.
- The two CLI gaps (`graph calendar status`, `data-quality table-inventory`) are known and assigned.

**Condition on Prompt 01:** treat R1 (ruff) and R2 (version-pin tests) as the explicit remediation /
quarantine targets; document R3 (weekend) as environmental; decide R4 (mart CHECK coverage) as an
additive-migration fix vs documented defensive-DDL note; resolve R5 (table-inventory) by
implementing or de-referencing it. No implementation may persist raw bodies or mutate any source
system.

**Prompt 00 (gap audit) complete.**

---

## 5. Remediation Outcomes (Prompt 01)

**Run UTC:** 2026-05-31 (Prompt 01) · Baseline before edits: HEAD `af6551e` (`main`), schema **V21**.
All commands under `source .venv/bin/activate`. Audit-only Prompt 00 → remediation Prompt 01.

### 5.1 Resolution of the 07A-residual blockers

| # | Blocker | Resolution | Verification |
|---|---|---|---|
| R1 | `ruff check .` exit 1 (24 issues) | **Fixed.** SIM105→`contextlib.suppress`, F401 removed, I001 sorted, B007 (`safety.py`) → `if pat.search`, B011 (`test_data_quality_gates.py`) → `raise AssertionError`, F841 (`test_relationship_quality.py`) removed. **No repo-wide `ruff format`** (would have churned 219 unrelated files). | `ruff check .` → **0** |
| R2 | ~20 migration version-pin test failures (`apply()==19/20`) | **Fixed durably.** Added `LATEST_SCHEMA_VERSION = 22` constant in `migrator.py`; the 9 test files now assert against it (auto-tracks future bumps). Stale `# reaches v15` comments removed. | the 9 files pass; `pytest` safe subset → 0 |
| R3 | 4 weekend-dependent `test_automation.py` failures | **Fixed (test-only, deterministic).** Each now sets `orch.cfg = MorningRunConfig(..., weekend_behavior="run", ...)` (mirrors the existing `test_orchestrator_render_basic` idiom) so the weekend gate never trips. No production change. | `test_automation.py` → 13 passed any day |
| R4 | `no-writeback-proof` exit 3 (5 V21 marts lack CHECK) | **Fixed (additive V22).** New `v22_mart_raw_body_guardrail` migration adds `raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0)` to the 5 marts via idempotent `ALTER TABLE ADD COLUMN` (SQLite rewrites `sqlite_master.sql`; prover detects it). V1–V21 untouched. | `no-writeback-proof` → **0** (`proof_passed=true`) |
| R5 | `data-quality table-inventory --json` not implemented | **Implemented.** New `table_inventory.py` + CLI command; read-only live-schema introspection reconciled against a new canonical contract resource (`resources/json/table_lifecycle_status_contract.json`, seeded from the 07A manual inventory — the file 07A had referenced but never shipped). | `table-inventory --json` → **0** |

### 5.2 Quarantined (07B-net-new, deferred to Prompt 06 — NOT implemented here)

- B3 (`upsert_email_model_classification` missing): the 7 `tests/test_email_classifier.py` tests plus
  `test_email_model_classifications_schema_v14.py::test_upsert_get_list_round_trip_and_idempotent`
  are marked `@pytest.mark.xfail(reason="07B Prompt 06: …", strict=False)`. They flip to xpass when
  P06 implements the method. **8 xfail total.**

### 5.3 Post-remediation validation matrix (actual exit codes)

| Command | Before (P00) | After (P01) |
|---|---|---|
| `python -m compileall src tests` | 0 | **0** |
| `ruff check .` | 1 (24) | **0** |
| `mypy src` | 0 | **0** (153 files) |
| `pytest -m "not live and not integration and not manual"` | 1 (31 failed/1883) | **0** (0 failed / 1890 collected; 8 xfail) |
| `construction-agent validate --json` | 0 | **0** |
| `procore validate --json` | 0 | **0** |
| `graph files status --json` | 0 | **0** |
| `graph mail status --json` | 0 | **0** |
| `graph calendar status --json` | 2 (not impl) | **2** (still 07B Prompt 03 scope) |
| `data-quality gates --json` | 0 | **0** |
| `data-quality no-writeback-proof --json` | **3** | **0** |
| `data-quality table-inventory --json` | **2** (not impl) | **0** |

New tests added: `tests/test_data_quality_schema_v22.py` (V22 add/idempotent/intact/CHECK-enforced),
`tests/test_data_quality_table_inventory.py` (report shape + CLI exit 0).

### 5.4 Guardrail attestation (Prompt 01)

- No Microsoft 365 / Procore / SharePoint / OneDrive / Outlook / calendar mutation or writeback.
- V22 is a local additive schema change applied by the standard migrator path; no new `--apply`
  write path added; `table-inventory` is read-only introspection. No live external call performed.
- No raw email/calendar body, raw prompt, raw model response, token, secret, PEM, signed/download
  URL, raw delta link, or private value appears in any changed code, test, evidence, resource, or
  JSON. The new contract resource was scanned clean.
- No Phase 07D meeting-prep readiness claimed; 07D remains blocked.

### 5.5 Go / No-Go for Prompt 02

**GO — Prompt 02 (Calendar Schema And Source Registry) may proceed.** The local baseline is now
fully green (ruff 0, mypy 0, safe pytest 0, no-writeback-proof 0), `table-inventory` is implemented,
and the V21 mart guardrail gap is closed at V22. No hidden blockers remain; the only non-green CLI
(`graph calendar status` exit 2) is the explicit subject of Prompt 03.

**Prompt 01 (07A remediation preflight) complete.**
