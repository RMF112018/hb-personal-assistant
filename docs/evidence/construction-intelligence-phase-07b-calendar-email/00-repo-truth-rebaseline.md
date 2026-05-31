# Repo Truth Rebaseline — Phase 07B Prompt 00

**Date:** 2026-05-31
**Phase:** 07B — Calendar & Email Thread Intelligence Foundation
**Prompt:** 00 — Repo Truth Audit And 07A Gap Inventory
**Run UTC:** 2026-05-31T10:33:13Z

**Baseline (pre-Prompt 00):**
- Branch: `main`
- HEAD: `3cf1652bf55303ceea25b2bbc6b5b1785111a335`
- Package version: `1.3.0` (`pyproject.toml`, `src/hb_assistant/__init__.py`)
- Schema/migration version: **V21** (`v21_agent_ready_query_marts`, `src/hb_assistant/store/migrator.py`)
- Working tree: only untracked `.claude/` (local agent config; not part of this prompt's change)
- This prompt is **documentation/evidence only** — no source code, no external-system call,
  no local SQLite mutation. All commands below are read-only / dry-run.

**All CLI/Python commands in this proof were executed with the project virtual environment
activated:**

```bash
source .venv/bin/activate && <command>
```

> **Redaction note.** `graph files status` and `graph mail status` emit private values
> (delegated UPN, tenant GUID, cache paths). Those raw values are **not** reproduced here; only
> non-sensitive structural facts (ok flag, auth classification, scope-presence booleans) are
> recorded. No token, secret, body, signed URL, or raw delta link appears in this file.

---

## 1. Repo-truth preflight

```bash
git rev-parse --abbrev-ref HEAD          # exit 0
git rev-parse HEAD                       # exit 0
git status --short                       # exit 0
```

**Output (redacted):**
```
main
3cf1652bf55303ceea25b2bbc6b5b1785111a335
?? .claude/
```

```bash
source .venv/bin/activate && python -m compileall src tests     # exit 0
```
**Output:** all packages listed and compiled; no errors.

```bash
source .venv/bin/activate && ruff check .                       # exit 1
```
**Output (summary, 24 errors):**
```
17  SIM105  suppressible-exception
 3  F401    unused-import
 1  B007    unused-loop-control-variable
 1  B011    assert-false
 1  F841    unused-variable
 1  I001    unsorted-imports
Found 24 errors. (4 fixable with --fix)
```
Affected files (all Phase-07A data-quality surfaces / their tests):
`src/hb_assistant/construction/data_quality/marts.py` (7),
`src/hb_assistant/construction/data_quality/safety.py` (3),
`src/hb_assistant/construction/data_quality/__init__.py` (1),
`tests/test_source_record_map.py` (4), `tests/test_relationship_quality.py` (4),
`tests/test_data_quality_gates.py` (2), `tests/test_data_quality_safety_proof.py` (1),
`tests/test_data_quality_obsidian_outputs.py` (1), `tests/test_agent_ready_query_marts.py` (1).

```bash
source .venv/bin/activate && mypy src                           # exit 0
```
**Output:** `Success: no issues found in 152 source files`
(note: `pyproject.toml` reports unused override section `hb_assistant.retrieval.context`).

```bash
source .venv/bin/activate && pytest -m "not live and not integration and not manual"   # exit 1
```
**Output:** 31 failed of 1883 collected (safe subset); remainder passed.
Failure taxonomy (see `01-phase-07a-gap-audit.md` for full classification):
- **20** migration version-pin assertions (tests assert `apply() == 19/20`; migrator now returns
  `21`) — stale test expectations, not regressions.
- **7** `tests/test_email_classifier.py` — `AttributeError: 'ConstructionStore' object has no
  attribute 'upsert_email_model_classification'` (the 07B `email_classifier_persistence_status`
  blocker, confirmed at runtime).
- **4** `tests/test_automation.py` — date-dependent: 2026-05-31 is a **Sunday**, orchestrator
  returns `skipped_weekend_manual_only`; tests expect `completed`/`error`.

---

## 2. Validation / command-availability matrix

| Command | Exit | Result (redacted) |
|---|---|---|
| `python -m compileall src tests` | **0** | compiles clean |
| `ruff check .` | **1** | 24 pre-existing issues (07A surfaces) |
| `mypy src` | **0** | no issues in 152 files |
| `pytest -m "not live and not integration and not manual"` | **1** | 31 failed / 1883 collected (see taxonomy) |
| `hb-assistant construction-agent validate --json` | **0** | schema_version=21; 6 projects/14 sources; 25 review rules; model routing ok |
| `hb-assistant procore validate --json` | **0** | 28/28 checks passed |
| `hb-assistant graph files status --json` | **0** | ok=true; delegated mode; token_type=delegated |
| `hb-assistant graph mail status --json` | **0** | ok=true; mail_read_scope_present=true; forbidden_mail_scopes_requested=[] |
| `hb-assistant graph calendar status --json` | **2** | `No such command 'calendar'` — **NOT implemented** (07B Prompt 03 work) |
| `hb-assistant construction-agent data-quality gates --json` | **0** | 13 gates; 07B blockers `deferred_not_blocking` (see §3) |
| `hb-assistant construction-agent data-quality no-writeback-proof --json` | **3** | code/import/secret scans pass; 5 V21 mart tables lack `raw_body_persisted=0` CHECK (see §4) |
| `hb-assistant construction-agent data-quality table-inventory --json` | **2** | `No such command 'table-inventory'` — **NOT implemented** |

---

## 3. `data-quality gates --json` — gate matrix (exit 0)

`run_id=phase07a-gates-2026-05-31T10-31-59`, `repo_sha=3cf1652…`, `schema_version=21`.

| Gate | Status | Blocking | Observed | Threshold | Future phase |
|---|---|---|---|---|---|
| project_identity_coverage | not_applicable | 0 | (none) | 1.0 | — |
| source_record_map_coverage | warning | 0 | 0.0 | 0.8 | — |
| deterministic_orphan_rate | pass | 0 | 0.0 | 0.02 | — |
| candidate_orphan_rate | pass | 0 | 0.0 | 0.1 | — |
| **email_classifier_persistence_status** | **deferred_not_blocking** | 0 | False | — | **07B** |
| **calendar_population_status** | **deferred_not_blocking** | 0 | False | — | **07B** |
| document_card_population_status | deferred_not_blocking | 0 | False | — | 07C |
| financial_amount_parseability | warning | 0 | 0.0 | 0.99 | 08B |
| financial_currency_completeness | warning | 0 | 0.0 | 0.95 | 08B |
| review_required_routing_presence | deferred_not_blocking | 0 | False | — | — |
| raw_content_leakage_scan | pass | 0 | 0 | 0 | — |
| external_writeback_scan | pass | 0 | 0 | 0 | — |
| query_latency_p95 | pass | 0 | ~0.015 ms | 500 ms | — |

**phase_go_nogo** (verbatim):
```json
{
  "07A_exit": { "ready": false, "blocking_gates": [] },
  "07B": { "blocked_by": ["email_classifier_persistence_status", "calendar_population_status"],
           "ready_for": ["calendar_ingestion", "email_thread_summaries", "meeting_project_matching"] },
  "07C": { "blocked_by": ["document_card_population_status"],
           "ready_for": ["document_card_population", "file_to_record_relationships"] },
  "07D": { "relationship_quality_ready": true,
           "notes": "07D can proceed on deterministic relationships even if candidate rates are warnings." },
  "08B": { "financial_readiness": "blocked" }
}
```

---

## 4. `data-quality no-writeback-proof --json` — safety proof (exit 3)

`phase="Phase 07A Prompt 08"`, `schema_version=21`, `ok=false`, `proof_passed=false`,
`no_live_call_performed=true`.

| Check | Passed | Findings |
|---|---|---|
| static_writeback_scan_07a_modules | ✅ | none |
| no_http_client_or_mutation_imports_07a | ✅ | none |
| module_secret_scan_07a | ✅ | none |
| sqlite_raw_body_guardrail_v20_v21_07a_tables | ❌ | 5 tables missing `CHECK(raw_body_persisted = 0)` |

Tables missing the CHECK (defensive-DDL gap, **not** a raw-body leak):
`project_source_coverage_mart`, `data_quality_gate_results`, `source_record_summary_mart`,
`relationship_quality_mart`, `cross_domain_context_readiness_mart`.
(Tables `construction_data_quality_runs`, `source_system_record_map`,
`relationship_resolution_queue` already carry the CHECK.)

---

## 5. Local-store population (read-only `SELECT COUNT(*)`)

```
email_thread_summaries     = 0
calendar_events            = 0
email_model_classifications = 0
```
All three 07B-relevant tables are present but empty, consistent with the gates above.

---

## 6. Guardrail attestation

- No Microsoft 365 / Procore / SharePoint / OneDrive / Outlook / calendar mutation or writeback
  performed. No POST/PUT/PATCH/DELETE/send/move/upload/permission/label/category change.
- No live external call: `no_live_call_performed=true`; `graph * status` ran in offline posture
  (token acquired only by `--apply`/`--download`, which were not invoked).
- No local SQLite write: every command was read-only or dry-run; no `--apply` was passed.
- No raw email/calendar body, raw prompt, raw model response, token, secret, PEM, signed URL,
  download URL, raw delta link, or private payload value appears in this file. Private auth
  values (UPN, tenant GUID, cache paths) were redacted to structural facts only.
- No Phase 07D meeting-prep readiness claimed. 07D remains explicitly blocked pending 07B/07C gates.

**Prompt 00 (rebaseline) complete.**
