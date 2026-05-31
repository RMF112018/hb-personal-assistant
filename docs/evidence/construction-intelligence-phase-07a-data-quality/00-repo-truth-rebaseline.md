# 00 — Repo Truth Rebaseline and Table Lifecycle Inventory (Phase 07A Prompt 00)

**Date:** 2026-05-31  
**Prompt:** 00 of HB_Construction_Intelligence_Phase_07A_Data_Quality_Canonical_Identity_Package  
**Objective:** Establish exact current repo truth and classify every SQLite table family before implementation begins. No schema/runtime changes.

## Global Guardrails (observed / enforced)

- No branch or worktree created.
- No external-system writeback.
- No raw email bodies, Procore payloads, Graph delta links, tokens, secrets, or PEMs persisted.
- No final legal/contractual/claims/safety/financial/schedule determinations.
- Deterministic vs heuristic candidates distinguished (in classification).
- Human review required for sensitive/high-impact (review queues preserved).

## 1. Git + Version Baseline

- **HEAD:** `cb526668b851d43b9e6c3b3116b297552f105526`
- **Branch:** `main`
- **Status (porcelain):** 7 modified evidence files (phase-06-email operational outputs + mvp-local-runtime markers; all pre-existing user work unrelated to 07A) + 2 untracked generated dirs (`.claude/`, `.code-graph/`). **No user work would be overwritten by adding only the new 07A evidence dir + architecture appends.**
- **Recent commits (top 5):** 
  - `cb52666` phase-06b prompt-14: procore retrieval readiness
  - `b758469` phase-06b prompt-13: obsidian operational outputs
  - `877e28c` phase-06b prompt-12: operational CLI surface
  - `ee4550a` phase-06b prompt-11: responsible party & relationship quality diagnostics
  - `8ec77b5` phase-06b prompt-10: schedule exposure model
- **Tags:** none.
- **Package version (source of truth):** `1.3.0` (pyproject.toml `[project] version`).
- **Package version (runtime metadata):** `0.9.0` (venv importlib; source pyproject authoritative; venv not reinstalled in this session).
- **Migration version:** V19 (confirmed via `SQLiteMigrator().current_version()` on local DB metadata = 19; full V1-V19 DDL in `src/hb_assistant/store/migrator.py` + 4 legacy tables outside migrator in `repositories.py`).

**Stop conditions checked:** uncommitted work exists but selective add of *new* paths only does not overwrite; V19 determinable from code + DB metadata; no secrets/raw in any output; zero live external calls (Graph/Procore/Ollama) performed.

## 2. CLI Surface Inventory (relevant to construction-agent, graph mail/files, procore)

**Root registration** (`src/hb_assistant/cli/main.py:60-69`):
- `auth`, `diagnostics`, `files`, `actions`, `search`, `run`, `automation`
- `construction-agent` (major nested group)
- `procore` (major nested group)
- `graph` (major nested group)
- Stubs: `vault`, `sync`, `brief` (thin "not implemented" with JSON contract)

### construction-agent (`src/hb_assistant/cli/construction.py`)
- `sources` (list, validate)
- `graph` (auth status, sources resolve, delta) + nested `sources`
- `sync`
- `vault` (bootstrap, preview)
- `review` (evaluate, list)
- `classify` (run, decisions)
- `ollama` (status)
- `index` (status)
- `validate` (multi-layer: schema + source_registry + review_rules + model_routing; --json default; used in validation matrix)
- `fixtures` (validate)

~35+ subcommands; 90%+ support `--json` + dry-run posture. Guardrails in docstrings + `_INDEX_GUARDRAILS`.

### graph (`src/hb_assistant/cli/graph.py`)
- `mail` (status, folders, index, discover, relationships, review-queue, classify, obsidian, operational-validate)
  - `body` (show — controlled decrypt)
- `files` (status, sites, drives, onedrive, index, crawl, delta, project-match, ingestion-policy, extract, review-queue, obsidian, retrieve, sources, no-writeback-proof)
  - `site` (resolve)
  - `link` (resolve)
- Broad `Files.*Write*` scopes noted as deferred risk (not tightened in 06A).

~20+ commands; dry-run default everywhere; explicit `--apply`/`--download`/`--extract` gates; no-writeback self-test + proof command.

### procore (`src/hb_assistant/cli/procore.py`)
- `auth` (status, login, refresh, logout)
- `tools` (list, catalog, audit [dry-run default, execute opt-in])
- `mapping` (validate, list)
- `projects` list, `companies` list
- `audit` (dry-run, execute)
- `sync` (run — Prompt09 pilot, dry-run default)
- `live` (fail-closed scaffolding)
  - `endpoints` (list, ledger)
  - `sync`, `inspect`, `smoke`, `history`, `changes`, `timeline`, `actions`
  - `project-health`, `stale`, `coverage`, `coverage-matrix`
  - `overdue`, `responsible-party-gaps`, `relationship-quality`, `digest`, `risks`, `retrieval-ready`, `no-writeback-proof`
  - `records` (count)
  - `financial` (summary, contracts, changes, invoices, budget, risk, exposure, coverage)
  - `schedule` (exposure)
- `obsidian` (preview, enriched, financial, project-health, meeting-prep, daily-digest, register)
- `validate` (CLI surface + seeds + mapping + redaction + templates + schema + auth)

~45+ commands; heavy use of live_* (V6/V7/V8/V9), obsidian deterministic output (Prompt10), 06B operational intelligence read models. All read-only; dry-run default; explicit gates; fail-closed live paths.

**Other surfaces (for completeness):** `diagnostics` (env, paths, auth, graph, scan-sensitive, automation, proof, mail, calendar, store, classify, brief, files — many with --json + sensitive redaction); `files` (sample, ingest); `actions` (extract, list); `run` (morning); `automation` (install/uninstall/kickstart launchd).

**Overall posture:** >90% of relevant commands are read-only / dry-run default / --json capable. No writeback paths active without explicit opt-in. Construction + procore + graph mail/files cover the Phase 06/06A/06B/07A surfaces.

## 3. Evidence Folders + README / Architecture Status

**Evidence layout (Shell find -maxdepth 2):**
- `construction-intelligence-phase-01` through `-06b-procore-operational-intelligence` (full arc 01-06B)
- `construction-intelligence-sharepoint-onedrive` (06A files)
- `mvp-local-runtime/` + subdirs (outputs, validation)
- `phase-0*` to `phase-14*` validation outputs + repo-truth-audit
- `remediation/`, `remediation-addendum/`, `remediation/final-closeout/`
- `prompt-*-delegated-proof/`, `vault-package-migration/`, `phase-14-local-runtime-workstream-intelligence/prompt-*`
- **Absence confirmed:** `docs/evidence/construction-intelligence-phase-07a-data-quality/` (no prior 07A work)

**README.md (head + prior full):** Repository Status block documents through Phase 06A closeout (Prompts 00-17, V19, 1698 tests, no-writeback proof). No mention of Phase 06B operational intelligence or Phase 07A. "Email Intelligence (Deferred)" section still references the old deferred policy (V5 table). Drift: README caps at 06A; 06B/07A evidence and work not yet reflected.

**docs/architecture/00-README.md (96 lines):** Long historical prompt log (Phase 1 through 06A + many remediation addenda). Lists 00-18 architecture records + remediation/*. Last entries pre-07A. No Phase 07A section. 05-store doc referenced as V5-era.

**docs/architecture/05-local-state-store-and-source-link-registry.md (100 lines, 2026-05-25 mtime):** Describes "Phase 5" / v0.5.0 / 10 core tables / V5 canonical. Completely outdated vs current V19 (80+ tables across 9+ families, procore V6-V9, email V10-V14, file V15-V19). Drift: must be updated or noted as historical.

**Conclusion:** Significant documentation drift. 07A Prompt 00 will produce the authoritative rebaseline + lifecycle inventory; architecture 00-README will receive a surgical append (this prompt only).

## 4. SQLite Schema Families + Report Reconciliation

**Extraction method:** Grep (Shell + tool) for all `CREATE TABLE IF NOT EXISTS` / `CREATE VIEW` in `migrator.py` (V1-V19 statements) + targeted Grep in `repositories.py` (legacy 4). No other CREATE sites in `src/`. Full DDL in migrator (additive only, never destructive). V4 statements appear after V7 in source but are applied in version order in `apply()`.

**Complete user table count:** 82 (per package report + extraction reconciliation; minor internal `schema_migrations` + legacy variance).

**Reconciliation to package 03_ report (key findings mapped to work):**
- 82 tables / 53 populated / 29 empty → this inventory + classification (Prompt 00 deliverable).
- Procore strong on tropical + records/syncs/snapshots/events/edges/actions/financials → preserve + map (07A source-record map).
- Missing Procore status/timestamps/numbers/titles → 07A+ endpoint completeness (not in this prompt).
- Financial dense/uneven → flag; defer 08B.
- Graph inventory exists / intelligence-light → track readiness (07C).
- Email metadata active → map to source-record (07A).
- Calendar absent, email thread summaries empty, embeddings empty → blocking classifications + 07B/09 notes.
- Cross-domain linkage incomplete → 07A source-record map + diagnostics; 07D promotion.

**Full family + lifecycle classification:** See companion `01-table-lifecycle-inventory.json` (machine-readable, all required fields, notes + V# + report refs) and `01-table-lifecycle-inventory.md` (human summary, matrix, rationale).

**Key classified tables (excerpt):**
- operational_populated (53): procore_live_*, most procore_financial_*, procore_*_entities / action_signals / inspection_*, email_messages/recipients/relationship_candidates/review_queue, construction_drive_items + file intel operational tables, core source_records/emails/attachments/action_items, etc.
- operational_empty_blocking (6): construction_project_identity / project_source_matches / document_cards (07A), calendar_events / email_thread_summaries (07B).
- placeholder_deferred (1): content_embeddings (09).
- legacy_superseded (8): old V2/V3 construction_* (inventory/review/resolutions), 4 procore_sync_* pilot (03/P09).
- evidence_only (~14): all *_receipts, *_crawl_runs, construction_model_decisions, processing_receipts, sync_errors, etc.
- 2 views: operational_populated (convenience over live data).

No `unknown_requires_audit`.

## 5. Validation (to be executed post-write)

See plan + package `11_VALIDATION_AND_EVIDENCE_REQUIREMENTS.md`:
```bash
python -m compileall src tests
ruff check .
mypy src
pytest -m "not live and not integration and not manual"
hb-assistant construction-agent validate --json
```

Outputs will be captured in evidence and referenced in commit.

## 6. Files Produced (this prompt only)

- `docs/evidence/construction-intelligence-phase-07a-data-quality/00-repo-truth-rebaseline.md` (this file)
- `01-table-lifecycle-inventory.json`
- `01-table-lifecycle-inventory.md`

## 7. Architecture Update (post-evidence)

Surgical append to `docs/architecture/00-README.md` (new dated section for Prompt 00) + optional note in 05-store doc. No other arch changes.

## 8. Commit

Traditional manifest-titled commit on `main` (no branch). Only the 3 new evidence files + 1-2 arch edits staged. Pre-existing modified evidence files left untouched.

**Manifest reference:** HB_Construction_Intelligence_Phase_07A_Data_Quality_Canonical_Identity_Package (Prompt 00).

All guardrails, no-writeback, read-only posture, and "repo code/tests/evidence as source of truth" observed.

**Prompt 00 complete.** Ready for Prompt 01 (V20 schema + repositories).