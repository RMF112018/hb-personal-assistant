# ADR 267 — Forecast Phase 11: controlled temp-DB preparation + readiness rehearsal

- **Status:** Accepted
- **Date:** 2026-06-18
- **Phase:** Forecast JSON/JSONL → SQLite transition, Phase 11
- **Builds on:** ADR 258–266 (Phases 2–10); v58 (PR #29), lifecycle contract (PR #30), Phases 2–10 (PRs #31–#39, Phase 10 merge `4e89204`).

## Context

Phase 10 added the DB-cutover **readiness gate** but deliberately **deferred temp-DB preparation** —
it consumes an already-prepared non-live v59 DB. That left an operational gap: no controlled command
goes from explicit Tropical source data to readiness evidence. Phase 11 closes it with a **rehearsal
workflow**:

    explicit Tropical source package -> non-live temp v59 DB (migrate + project) -> Phase 10
    readiness gate -> deterministic rehearsal evidence report.

Phase 11 is still **not** a production default flip: no live/default DB writes, no DB-backed reads as
default, no final integrated CSV from DB, no model-backed/intelligence/comprehensive/probability/
monthly workflows, no new domain migration beyond the existing v59 source-domain projection.

## Decision

### New CFR-only rehearsal module (orchestration reuse)

New `workflows/temp_db_readiness_rehearsal.py`, above the Phase 10 gate. It owns preflight + temp-DB
preparation + the rehearsal report, and **reuses** the Phase 10 `run_db_cutover_readiness(...)`
(which itself reuses the Phase 9 parity). CFR-only / stdlib at import time; `hb_assistant`
(`SQLiteMigrator`, `source_domain_engine`) is imported **lazily, only inside the explicit
DB-preparation path** (the live-DB check uses a module-ref call so tests monkeypatch it cleanly).

API: `run_temp_db_readiness_rehearsal(*, source_package, work_root, context_stamp, db_path=None, project_key="tropical") -> dict`.

### Preflight (fail closed, before any output)

`project_key == "tropical"`; `source_package` exists, is a directory, is named
`twn_cost_forecast_json_package`, and has the three `data/*.jsonl` members (budget details, cost
entries, monthly actuals); `work_root` explicit and not under the live Synology root; `context_stamp`
nonempty; and the temp DB path resolved/validated. `data_root` for the Phase 10 gate is
`source_package.parent` (the data root holding the sibling owner/procore packages the context
generator reads). Missing siblings surface later via the existing readiness/parity fail-closed path.

### DB path contract

If `db_path` is omitted, it is derived as
`<work_root>/temp_dbs/forecast_source_domain_tropical.sqlite`. If provided, it must be **under**
`work_root` (BOTH paths `.resolve(strict=False)`-d and checked with `is_relative_to`, so symlinks /
`..` cannot escape), must **not** be the live/default DB (`is_live_db_path`, fails closed), must have
a creatable parent, and must **not already exist** (no reuse — keeps the rehearsal deterministic; no
`overwrite`/`reuse` flag). A pre-existing DB or a non-empty `work_root` fails closed.

### DB preparation

`SQLiteMigrator(db_path=str(db_path)).apply()` (migrates to LATEST = 59, creates the v59 tables) →
verify `MAX(schema_migrations.version) >= 59` → `source_domain_engine.project_source_domain(source_package=..., project_key="tropical", db_path=..., apply=True)` (fails closed
`apply_requires_explicit_db_path` / `apply_refuses_live_db`) → read-only count of
`project_key='tropical'` rows in each required v59 table. A projection failure or any empty required
table fails closed. Required tables: `forecast_budget_details`, `forecast_cost_entries`,
`forecast_monthly_actuals_by_budget_code`. No new schema, ingestion tables, or projection rewrite.

### Decision values + CLI rc mapping

After successful prep the Phase 10 gate runs. Readiness `ready_for_guarded_operator_use` → rehearsal
`status: passed` (CLI rc 0); readiness `not_ready` → `status: failed` (CLI rc 1). Any
unsafe/missing/ambiguous input or DB-prep/projection failure → `TempDbRehearsalError` (CLI rc 3),
before/without a clean report.

### Deterministic rehearsal report

`schema_version: 1`, sorted-key JSON, trailing newline, **no wall-clock**. Shape: `project_key,
status, decision, source_package, data_root, work_root, context_stamp, db{path, created,
schema_version, live_db_refused}, projection{applied, required_tables{<tbl>:{rows}}},
readiness{decision, report_path}, safety{...}`. Written to
`<work_root>/temp_db_readiness_rehearsal_report.json`; the returned dict adds `report_path`. The
`safety` block is grounded in this run's preflight + explicit-path checks (work root verified outside
the live root; temp DB verified not the live DB) — not a global filesystem audit.

### Additive CLI command

`temp-db-readiness-rehearsal --project tropical --source-package <twn_cost_forecast_json_package> --work-root <non-live work root> --context-stamp <stamp> [--db-path <temp under work root>]` — clean
JSON to stdout, rc 0/1/3 as above. All existing commands (`db-cutover-readiness`,
`controlled-context-analysis`, `context-generate`, `final-forecast-generate`,
`package-chain-manifest`, `run-context`, `run-analysis`, all generators) are unchanged.

### Included: a minimal Phase 9 parity-normalizer hardening fix (discovered during Phase 11)

Phase 11's repeated parity runs surfaced a **pre-existing latent flake** in the Phase 9 parity
comparison (it passed Phase 9/10 CI only by luck). The analysis generator embeds its wall-clock
"generated" stamp as **plain text** in `README.md` / `forecast_review_summary.md` (`generated
<stamp>`), not only inside the package directory name. Phase 9's analysis normalizer
(`controlled_db_context_analysis._load_package_outputs`) stripped the full dir name but not the bare
stamp, so when the file-mode and db-mode analysis subprocesses straddled a 1-second boundary, those
two markdown lines differed → analysis parity `fail` (~1/8) → readiness `not_ready` → rehearsal
`failed`.

The fix is a **minimal, backward-compatible volatility-normalization hardening** of the Phase 9
comparison helper: after replacing the full package dir name, also neutralize the bare package stamp
substring (`<STAMP>`). It is **not** a generation behavior change — the analysis generator
(`generate_forecast_analysis_package.py`) is untouched, operator-facing package content is unchanged,
and no CLI/default/schema/DB behavior changes. A regression test
(`test_parity_normalizes_bare_analysis_generated_stamp`) reproduces the bare-stamp condition and
asserts the normalizer collapses it; the Phase 9 parity test and Phase 11 rehearsal tests are now
stable (0 failures over repeated stress runs). The context-package stamp is identical on both sides,
so neutralizing it there is a no-op.

## Real-data smoke command (documentation only — never executed in tests)

```bash
python -m construction_financial_review.cli temp-db-readiness-rehearsal \
  --project tropical \
  --source-package "<Tropical data root>/twn_cost_forecast_json_package" \
  --work-root "<non-live temp rehearsal root>" \
  --context-stamp "<operator-chosen stamp>"
```

The temp DB is created under the work root and projected from the explicit source package; the live
DB and live Synology root are never written.

## v58 resolver + final integrated CSV — STILL DEFERRED

The v58 `forecast_package_manifests` DB resolver and final integrated forecast CSV DB generation
remain deferred and are not implemented here.

## Live safety

No Phase 11 test writes under the live Synology root or touches the live/default DB. All source
fixtures, temp DBs, packages, and reports are under `tmp_path`; the temp DB is migrated/projected
read-write but is verified non-live first; readiness inspection is read-only.

## Test strategy

`tests/test_forecast_temp_db_readiness_rehearsal_phase11.py` (mirrors the Phase 9/10
fixture/projection pattern): success with derived + explicit temp DB → passed; deterministic report;
report content coverage (migration/projection/required-table counts/readiness decision + report
path); the fail-closed guard matrix (unsupported project, missing source, invalid structure,
live-root work root, db_path outside work root, live db_path, pre-existing db_path, pre-existing
work-root output); not_ready → failed (stubbed readiness); CLI success (derived + explicit), CLI
refusal rc 3, CLI not-ready rc 1; existing-command route preservation. Plus the Phase 9 regression
test above. All outputs under `tmp_path`; temp SQLite only; no Synology.

## Scope / deferrals

Production DB-backed default enablement; global latest-glob/config-pin/run-state replacement; the v58
package-manifest DB resolver; final integrated forecast CSV DB generation;
intelligence/comprehensive/model-backed parity; full DB domain migration beyond v59 source domain;
owner/Procore/control/staffing/schedule DB reads; the −$3.42M reconciliation; class-based generator
cleanup.

## Consequences

- **No schema change** (`LATEST_SCHEMA_VERSION` stays 59; no v60). **No lifecycle-contract change** (`table_count` stays 387). **No `hb_assistant` source change** (lazy reuse of existing migrate/project/live-DB helpers only).
- An operator can run one explicit command from source package → temp non-live v59 DB → v59 projection → Phase 10 readiness evidence, with production defaults and live data untouched.
- Changed surface: one new CFR rehearsal module, one new CFR CLI subcommand, one new test module, this ADR, **plus** a minimal Phase 9 parity-normalizer hardening fix (+ its regression test).
- Live DB untouched (still v58, no v59 domain tables); no live-root output written.
```
