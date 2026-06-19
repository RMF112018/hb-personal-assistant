# ADR 270 — Forecast Phase 14: controlled live DB source-domain projection

- **Status:** Accepted
- **Date:** 2026-06-19
- **Phase:** Forecast JSON/JSONL → SQLite transition, Phase 14
- **Builds on:** ADR 258–269 (Phases 2–13); v58 (PR #29), lifecycle contract (PR #30), Phases 2–13 (PRs #31–#42, Phase 13 merge `19932438`).

## Context

Phase 13 ran the live/default DB audit + certification against the **real** DB: schema v59, the three
v59 source-domain tables present but **empty** (zero tropical + zero total rows) → certification
`schema_only`. A fresh temp projection from the Tropical source produces
`forecast_budget_details=127`, `forecast_cost_entries=6324`,
`forecast_monthly_actuals_by_budget_code=1081`. So the live DB is structurally ready but not yet
populated, and not yet eligible for the Phase 13 certified-equivalence guarded opt-in.

**Phase 14** is the FIRST workflow permitted to write the live DB — narrowly, gated, reversible:

    fresh non-live temp projection (migrate + project) -> verify -> BACKUP the live DB -> ONE
    transaction replacing only project_key='tropical' rows in the three v59 tables with rows copied
    from the temp DB -> deterministic evidence -> rerun Phase 13 certification (require certified_match).

### Why a v59 schema-only live DB is safe to populate under explicit gates

The live DB already has the correct v59 schema and zero source-domain rows; populating it is purely
additive for tropical. Safety comes from: an explicit `allow_live_db_write` gate; a verified
byte-for-byte backup taken before any write; building/validating the data in a non-live temp DB first
(the live DB is never migrated or directly projected); a single transaction that touches only the
three v59 tables' tropical rows (non-tropical rows preserved); in-transaction row-count verification
with rollback on any failure; and a mandatory post-write Phase 13 `certified_match` certification.

This is **not** a production default cutover: no DB-backed reads/resolution default, no file-backed
path removal, no final integrated CSV from DB, no intelligence/comprehensive/probability/monthly/
model-controls/LLM workflows, no live migration, no direct `project_source_domain(apply=True)` on the
live DB, no Phase 4/9 live read execution. **Invariants:** no schema change,
`LATEST_SCHEMA_VERSION==59`, lifecycle `387`, no `hb_assistant` source change.

## Decision

### New CFR-only module `workflows/live_db_source_domain_projection.py`

`run_controlled_live_db_source_domain_projection(*, source_package, work_root, context_stamp, live_db_path=None, project_key="tropical", allow_live_db_write=False, allow_replace_existing=False, run_guarded_operator_check=False, expected_counts=None) -> dict`.
`LiveDbSourceDomainProjectionError` (fail closed). Reuses Phase 13 `live_db_certification`
(`run_live_db_provenance_audit`, `run_live_db_readonly_certification`, `_ro_conn`, `_digests`,
`_raw_strings`, `_file_provenance`, `_resolve_live_db_path`, `_is_live_db`) and the migrator +
source-domain engine (temp DB only, lazy import).

**Live-write scope.** Only the three v59 tables — `forecast_budget_details`, `forecast_cost_entries`,
`forecast_monthly_actuals_by_budget_code` — and only their `project_key='tropical'` rows. No other
table or row is touched; non-tropical rows are preserved.

**Preflight (fail closed → rc3, before any output/backup/write):** project==tropical;
`allow_live_db_write` true; source package exists + named `twn_cost_forecast_json_package`; work root
explicit + not under the live root; context stamp nonempty; resolved path is the live/default DB and
exists; Phase 13 audit shows schema 59 + all three tables present; existing tropical rows refused
unless `allow_replace_existing=True`.

**Backup strategy.** Byte-for-byte `shutil.copy2` of the main DB file →
`<work_root>/backups/hb-personal-assistant.before-phase14.sqlite`, recording path/size/sha256, then
verified openable `mode=ro` at schema 59. The backup is never deleted by the workflow.

**WAL handling.** The DB is WAL-mode. The backup gate **fails closed (rc3)** if the pre-write WAL is
nonzero, because a byte copy of only the main file would miss WAL frames (no consistent-snapshot
mechanism is enabled in Phase 14; the real live DB's WAL was zero). A future phase may add the SQLite
online-backup API to relax this.

**Temp projection + expected counts.** Build a fresh temp DB under `<work_root>/temp_dbs/`
(`SQLiteMigrator.apply()` + `project_source_domain(apply=True)`), record per-table counts + dual
digests (byte-exact `raw_json` + canonical). `expected_counts` is **operator-supplied and optional**
(CLI `--expect-budget-details/--expect-cost-entries/--expect-monthly`): when provided, each table's
temp count must match exactly or the run fails closed (rc3) **before** backup/write, reporting
actual-vs-expected; when omitted, counts are recorded but not gated. The current real Tropical baseline
is **127 / 6324 / 1081** — observed from Phase 12/13 evidence, passed by the operator on the real run,
**not** hardcoded as a module constant.

**Transactional copy.** Open the live DB write connection; per table discover columns via
`PRAGMA table_info` and require identical column sets/order with the temp DB. In one
`BEGIN IMMEDIATE` transaction: `DELETE WHERE project_key='tropical'`, `INSERT` the temp rows (all
columns incl. `raw_json` + metadata), and verify live tropical `COUNT(*)` == temp count
(`_verify_inserted`); `COMMIT` only on full success, else `ROLLBACK` and raise.

**Post-write verification.** Reopen `mode=ro`; rerun Phase 13 audit + certification (separate
`<work_root>/post_write_cert` sub-root) and require decision `certified_match`. Success →
`decision='live_db_source_domain_certified'` / status `ready` (rc 0). Otherwise
`decision='not_ready'` (rc 1) with the backup path recorded.

**Optional guarded proof.** When `run_guarded_operator_check=True` and certified, run the Phase 12
certified-equivalence guarded operator run (`db_path=live`, `allow_certified_live_db=True`,
`live_db_certification=<post-write cert>`); expected `ready` / approved /
`live_db.used_for_execution==false` / `equivalent_to_temp_db==true` — proving the now-certified live DB
is accepted as evidence while execution still uses a fresh temp DB.

**Rollback posture.** No automatic destructive rollback. On any post-write certification failure the
report records the verified backup path for **manual** restore (copy the backup over the live DB). The
transaction itself rolls back atomically on in-flight failure.

### Additive CLI (cli.py — append only, not ruff-format-enforced)

`live-db-source-domain-project`: required `--project --source-package --work-root --context-stamp`;
flags `--allow-live-db-write`, `--live-db-path`, `--allow-replace-existing`,
`--run-guarded-operator-check`, `--expect-budget-details/--expect-cost-entries/--expect-monthly`.
rc 0 (`certified_match`) / 1 (post-write cert not matched) / 3 (refusal). All existing commands
unchanged.

## Real-data operator example (documentation only — never executed in tests)

```bash
python -m construction_financial_review.cli live-db-source-domain-project \
  --project tropical \
  --source-package "<Tropical data root>/twn_cost_forecast_json_package" \
  --work-root "<non-live work root>" --context-stamp "<operator stamp>" \
  --allow-live-db-write \
  --expect-budget-details 127 --expect-cost-entries 6324 --expect-monthly 1081 \
  --run-guarded-operator-check
```

The real live write is a separate operational execution requiring Bobby's explicit go-ahead; it was
not run during implementation/tests (synthetic DBs only).

## Test strategy

`tests/test_forecast_live_db_source_domain_projection_phase14.py` (24 tests). A synthetic "live" DB =
a migrated temp DB (empty / seeded), WAL-checkpointed (TRUNCATE), with `is_live_db_path` monkeypatched
to flag it. Covers preflight/gate refusals (no allow flag, non-live, missing source, unsafe work root,
missing live, schema<59, missing tables, nonzero WAL), backup creation+verification, temp build +
counts, expected-count match (1/2/2) and mismatch→rc3-before-write, three-table-only transactional
copy, non-tropical preservation, refuse/allow existing tropical, rollback on in-transaction failure
(content + non-tropical row intact + backup present), post-write audit + `certified_match`,
deterministic report + safety block, optional guarded proof, CLI rc 0/1/3. Synthetic only; the real
live DB is never touched (size/mtime confirmed unchanged across implementation + tests).

## Consequences

- A safe, gated, reversible path to populate the live DB's v59 tropical source-domain rows, certified
  equivalent to a fresh projection — making the live DB eligible for the Phase 13 certified-equivalence
  guarded opt-in.
- No schema change; `LATEST_SCHEMA_VERSION` stays **59**; lifecycle table count stays **387**; no v60;
  no `hb_assistant` source change.

## Deferred (unchanged by Phase 14)

- Production DB-backed default cutover; DB-backed reads/resolution as default.
- True read-only live execution (a `mode=ro` Phase 4/9 adapter path).
- Final integrated forecast CSV DB generation; the −$3.42M reconciliation.
- v58 `forecast_package_manifests` DB resolver.
- Intelligence/comprehensive/model-backed parity.
- Broader domain migration beyond v59 source; owner/Procore/control/staffing/schedule DB reads.
- Consistent-snapshot (online-backup-API) backup to relax the nonzero-WAL fail-closed gate.
- Class-based generator cleanup.
