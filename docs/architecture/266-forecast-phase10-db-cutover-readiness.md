# ADR 266 — Forecast Phase 10: controlled DB-cutover-readiness gate

- **Status:** Accepted
- **Date:** 2026-06-18
- **Phase:** Forecast JSON/JSONL → SQLite transition, Phase 10
- **Builds on:** ADR 258 (Phase 2 lineage), ADR 259 (Phase 3 v59 source-domain read parity), ADR 260 (Phase 4 DB read adapter), ADR 261 (Phase 5 context-generator parameterization), ADR 262 (Phase 6 controlled context generation), ADR 263 (Phase 7 controlled analysis parity), ADR 264 (Phase 8 package-resolution hardening), ADR 265 (Phase 9 controlled DB workflow); v58 (PR #29), lifecycle contract (PR #30), Phases 2–9 (PRs #31–#38, Phase 9 merge `c3cfeaa`).

## Context

Phases 6–9 delivered a controlled, default-off DB-backed context→analysis chain (runner → analysis
→ package resolution → chain manifest) and a Phase 9 workflow that runs it `file`/`db`/`parity` and
emits deterministic artifacts. What's still missing is a **readiness gate**: a single, auditable
operation that answers — *is the DB-backed chain safe for intentional, guarded operator use with
this explicit non-live DB and this explicit work root?* — and produces evidence for that decision.

Phase 9 alone is not enough: it can *run* the chain, but it does not **validate the prerequisites**
the DB-backed adapter depends on (a temp/non-live v59 DB with the right schema version and populated
source-domain tables) nor render a **ready / not-ready decision**. Phase 10 adds that gate. It is
still **not** a production default flip, not CSV generation, not a domain migration, and not the
deferred v58 `forecast_package_manifests` DB resolver.

This Phase-10 "DB cutover readiness" is **distinct** from the pre-existing Phase-08c
`forecast_readiness` gates (financial-fact readiness / Ollama / review-required) — a different
concept in different files. Phase 10 touches none of those.

## Decision

### New CFR-only readiness module (orchestration reuse, not duplication)

New `workflows/db_cutover_readiness.py`. It owns the **preflight checks**, the **read-only temp v59
DB inspection**, the **decision**, and the **evidence report**. It does **not** duplicate
orchestration: it calls the Phase 9 `run_controlled_context_analysis_parity(...)` to actually run the
file-backed vs DB-backed chain and compare. Phase 9 behavior is unchanged.

CFR-only / stdlib: the only `hb_assistant` touchpoint is a lazy, fail-closed live-DB check —
`db_cutover_readiness._refuse_if_live_db` imports the source-domain MODULE inside the check and calls
`source_domain_engine.is_live_db_path(db_path)` via the module reference (not a name bound at import
time), so tests monkeypatch the safety behavior cleanly. Schema/table inspection uses stdlib
`sqlite3` on a strictly read-only connection.

Primary API:

```
run_db_cutover_readiness(*, data_root, work_root, context_stamp, db_path,
                         project_key="tropical", run_parity=True) -> dict
```

### Refusal vs decision

- **Unsafe / missing / ambiguous inputs fail closed** (`DbCutoverReadinessError`) *before* anything runs → CLI rc `3`.
- Once preflight passes, the workflow runs and the **decision is data**: parity `pass` → `ready_for_guarded_operator_use` (status `ready`); parity `fail` → `not_ready` (a successful gate outcome — not a refusal). With `run_parity=False` only the DB-backed workflow runs (proving DB-backed execution) and the decision is `not_ready`, since file-vs-DB parity evidence is required to certify readiness; the CLI always runs parity.

### Preflight readiness checks (fail closed)

`project_key == "tropical"`; `data_root` exists and is a directory; `work_root` explicit and not
at/under the live Synology root; `context_stamp` nonempty; `db_path` explicit and existing;
`db_path` is not the live/default DB (`is_live_db_path`, fails closed on unresolvable); and the
read-only DB inspection below. Finally, `<work_root>/readiness` must not already hold output.

### Read-only temp v59 DB inspection

Opens a strictly read-only connection — `f"file:{urllib.parse.quote(str(db_path.resolve()))}?mode=ro"`
with `uri=True`, so paths containing spaces (e.g. "HB Personal Assistant") are safe and `mode=ro`
**never creates** a missing file (preflight has already checked `.exists()`). It then verifies, and
fails closed on any miss:

- the DB is a readable SQLite database;
- `schema_migrations` table exists;
- `MAX(version) >= 59` (`REQUIRED_SCHEMA_VERSION`, the version that introduced the v59 source-domain tables the DB-backed adapter reads — stable even if `LATEST_SCHEMA_VERSION` later rises);
- each required v59 source-domain table exists: `forecast_budget_details`, `forecast_cost_entries`, `forecast_monthly_actuals_by_budget_code`;
- each has at least one `project_key = 'tropical'` row.

These mirror exactly what the Phase 4/6 DB-backed adapter consumes — no broader inspection.

### Deterministic readiness report

`schema_version: 1`, sorted-key JSON, trailing newline, **no wall-clock timestamp**. Shape:
`project_key, status, decision, data_root, work_root, context_stamp, db_path,
db_checks{db_exists, live_db_refused, schema_version, required_tables_present,
required_tables_nonempty}, workflow{parity_report, file_report, db_report, file_chain_manifest,
db_chain_manifest}, parity{context_match, analysis_match, chain_match}, safety{...}`. Written to
`<work_root>/readiness/db_cutover_readiness_report.json`; the returned dict adds `report_path`.

The `safety` block (`production_defaults_changed: false`, `live_root_written: false`,
`live_db_written: false`) is **grounded** in this controlled run's preflight and explicit-path
checks (work root verified outside the live root; DB-backed path refuses the live DB) — it is **not**
a claim of a global filesystem audit.

### Additive CLI command

`db-cutover-readiness --project tropical --data-root <src> --work-root <work> --context-stamp <stamp>
--db-path <temp-v59.sqlite>` runs the gate (always parity), prints the clean JSON report to stdout,
and returns rc `0` (ready), rc `1` (not-ready evidence — gate ran, parity did not match), or rc `3`
(controlled refusal). All existing commands — `context-generate`, `final-forecast-generate`,
`package-chain-manifest`, `controlled-context-analysis`, `run-context`, `run-analysis`, and every
generator command — are unchanged.

## Temp-DB preparation helper — DEFERRED (documented)

Phase 10 **consumes** an already-prepared explicit temp v59 DB; it does **not** add an operator-facing
DB-prep CLI/helper (that would broaden `hb_assistant` coupling and scope). The existing operator/test
preparation path (used by the Phase 10 tests' `_project_db`) is:

```python
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.construction.forecast import source_domain_engine

SQLiteMigrator(db_path=str(temp_db)).apply()                      # migrate to v59 (creates tables)
source_domain_engine.project_source_domain(                      # populate from a source package
    source_package=<twn_cost_forecast_json_package>, project_key="tropical",
    db_path=temp_db, apply=True,                                 # fails closed: explicit + non-live DB
)
```

`project_source_domain` already fails closed (`apply_requires_explicit_db_path`,
`apply_refuses_live_db`), so this never writes the live DB.

## v58 `forecast_package_manifests` DB resolution — STILL DEFERRED

Per ADR 264/265, the read-only resolver against the v58 `forecast_package_manifests` table remains
deferred and is **not** implemented here. No `hb_assistant` reader, schema, DB resolver, or
package-manifest selection logic is added.

## Live safety

No Phase 10 test writes under the live Synology root or touches the live/default DB. All packages,
manifests, reports, and DBs are under `tmp_path`; DB inspection is read-only (`mode=ro`, no
creation); the live-DB guard refuses the default DB and any unresolvable path.

## Test strategy

`tests/test_forecast_db_cutover_readiness_phase10.py` (mirrors the Phase 9 fixture/DB-projection
pattern; `build_fixture`/`_wj`/`_wjson`/`_project_db` duplicated, not imported): readiness success →
`ready`; deterministic report; parity-fail → `not_ready` (stubbed parity); report includes
`db_checks` schema version + table coverage; refusals — unsupported project, missing data root,
missing/falsy db_path, live DB (monkeypatched `is_live_db_path`), missing `schema_migrations`,
schema < 59, missing v59 tables, empty v59 tables (migrated-not-projected), live-root work root
(monkeypatched `_LIVE_ROOT`), pre-existing readiness output; CLI success rc 0; CLI refusal rc 3; and
existing-command route preservation. Hand-crafted SQLite DBs cover the schema/table refusal cases.
All outputs under `tmp_path`; temp SQLite only; no Synology.

## Scope / deferrals

Production DB-backed default enablement; global latest-glob/config-pin/run-state replacement; the v58
package-manifest DB resolver; final integrated forecast CSV DB generation;
intelligence/comprehensive/model-backed parity; full DB domain migration;
owner/Procore/control/staffing/schedule DB reads; an operator-facing temp-DB prep helper; the
−$3.42M reconciliation; class-based generator cleanup. No Phase 11 / next-phase work.

## Consequences

- **No schema change** (`LATEST_SCHEMA_VERSION` stays 59; no v60). **No lifecycle-contract change** (`table_count` stays 387). **No `hb_assistant` source change** (Phase 10 is entirely CFR-only; only a lazy read-only call into the existing live-DB guard).
- The repo now has an explicit, auditable readiness gate that produces deterministic evidence for whether DB-backed context→analysis generation is safe for guarded operator use on an explicit non-live DB and work root — **without** making DB-backed reads, DB resolution, or anything else the default.
- Changed surface is additive: one new CFR readiness module, one new CFR CLI subcommand, one new test module, and this ADR.
- Live DB untouched (still v58, no v59 domain tables); no live-root output written.
