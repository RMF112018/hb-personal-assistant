# ADR 269 — Forecast Phase 13: live DB provenance audit, read-only certification & guarded live-DB opt-in

- **Status:** Accepted
- **Date:** 2026-06-18
- **Phase:** Forecast JSON/JSONL → SQLite transition, Phase 13
- **Builds on:** ADR 258–268 (Phases 2–12); v58 (PR #29), lifecycle contract (PR #30), Phases 2–12 (PRs #31–#41, Phase 12 merge `baf25f87`).

## Context

Phase 12 shipped a guarded DB operator-run manifest for the **non-live temp-DB** path. During Phase 12
validation the live/default SQLite DB was unexpectedly found already at **schema v59 with the three
v59 source-domain tables populated** — flagged as pre-existing, not caused by Phase 12, and out of
scope for PR #41. Before any live-DB operator eligibility can exist, that state must be **resolved
safely**: the live DB must be audited and, if populated, proven to MATCH a fresh non-live projection
from the explicit Tropical source package.

Phase 13 adds two strictly read-only operations plus a guarded opt-in gate. It is **not** a production
default cutover: no live-DB writes/migrations/projection, no DB-backed reads/resolution default, no
file-backed path removal, no final integrated CSV from DB, no
intelligence/comprehensive/probability/monthly/model-controls/LLM workflows, no domain migration
beyond the existing v59 source-domain projection. **Invariants held:** no schema change,
`LATEST_SCHEMA_VERSION == 59`, lifecycle table count `387`, no `hb_assistant` source change, v58
`forecast_package_manifests` resolver still deferred. The real live DB was confirmed byte-size + mtime
unchanged across the whole run (opened `mode=ro` only).

## Decision

### New CFR-only module `workflows/live_db_certification.py`

`LiveDbCertificationError` (fail closed). `hb_assistant` (PathPolicy, migrator, source-domain engine +
`source_domain_repository`) is imported lazily inside functions. The live DB is opened **only** via a
read-only URI (`file:<quoted>?mode=ro`); it is never created, migrated, projected, or written.

**`run_live_db_provenance_audit(*, live_db_path=None, work_root=None, project_key="tropical") -> dict`**
Strictly read-only. Preflight: project=tropical; resolve the live path if omitted; require it exists
and `is_live_db_path(...)` is true (this audit is *for* the live DB); fail closed if unreadable.
Reports filesystem provenance (size, mtime, WAL/SHM existence+size), schema version, full
`schema_migrations` history (`version`/`name`/`applied_at`), required-table presence, and
source-domain row counts by `project_key` (distinct keys, per-table tropical + total). Decision:
`populated_tropical` / `schema_only` (v59 tables, 0 tropical rows) / `populated_other_projects` /
`missing_v59_tables` / refusal. Writes `<work_root>/live_db_provenance_audit_report.json` when a
non-live `work_root` is given; always returns the dict.

**`run_live_db_readonly_certification(*, source_package, work_root, context_stamp, live_db_path=None, project_key="tropical") -> dict`**
Preflight (fail closed, no output first): project=tropical; `source_package` exists + named
`twn_cost_forecast_json_package`; `work_root` explicit + not under the live root; `context_stamp`
nonempty; live path exists + is the live/default DB. Then: (1) read-only audit; (2) build a fresh
**non-live** temp v59 DB under `work_root` (`SQLiteMigrator.apply()` + `project_source_domain(apply=True)`);
(3) read both DBs `mode=ro` and compare tropical source-domain rows per table. Decision:
`certified_match` (all tables match AND live has tropical rows) / `schema_only` (no live tropical rows)
/ `stale_or_mismatch` / `uncertified`. Writes `<work_root>/live_db_readonly_certification_report.json`.

### Comparison strategy — byte-exact + canonical, per table

For each required v59 table, the exact stored `raw_json` strings are read for `project_key='tropical'`
from both DBs and compared two ways, both **order-independent** (sorted before digesting):

- **byte-exact** `raw_json` digest — `sha256` over the sorted exact stored strings (true byte equivalence);
- **canonical row** digest — `sha256` over each row re-dumped `json.dumps(..., sort_keys=True)` (robust
  to JSON field ordering).

A table's `match` requires equal row counts **and** equal byte-exact digest **and** equal canonical
digest. `certified_match` requires `match` for all three tables. The report records per-table
`live_rows`/`temp_rows`/`raw_json_digest_*`/`canonical_digest_*`/`raw_json_match`/`canonical_match`/`match`
and a `mismatch_summary`. (The dual digest is why the report claims byte-exact equivalence, not merely
normalized row equivalence.)

### Guarded live-DB opt-in — certified-equivalence, NOT live execution

`run_guarded_db_operator_run(...)` gains `allow_certified_live_db: bool = False` and
`live_db_certification: Path | None = None`. The temp/non-live path is byte-identical to Phase 12. A
`db_path` that resolves to the live/default DB is **refused** unless `allow_certified_live_db` is set
AND a valid `live_db_certification` is provided. Validation (fail closed → `GuardedDbOperatorRunError`):
report exists and is not under the live root; `schema_version` match; `decision == certified_match`;
matching `project_key`; `live_db` resolves to the same `db_path`; `source_package` resolves to the same
source package; every required table `match` is true.

**Even when accepted, the live DB is never threaded into execution.** Certification has already proven
the live DB's v59 source-domain rows are equivalent to a fresh temp projection, so the guarded run
executes against a **fresh non-live temp DB** (Phase 11 with `db_path=None`) and stamps the manifest
with a `live_db` evidence block:

```json
{
  "certified": true,
  "certification_report": "<path>",
  "live_db_path": "<path>",
  "certification_decision": "certified_match",
  "equivalent_to_temp_db": true,
  "used_for_execution": false
}
```

The manifest still returns `ready` / `approved_for_guarded_db_context_analysis_use`; the `live_db`
block makes explicit that execution used the fresh temp DB, not the live DB. This was chosen over true
read-only live execution because Phase 11 (which Phase 12 reuses) migrates + projects its `db_path`,
and the Phase 4/9 DB adapter opens a read-write connection — neither is safe against the live DB.
**True read-only live execution remains deferred** until a separate phase proves the Phase 4/9 adapter
can use a strict `mode=ro` live connection end-to-end without weakening existing safety checks.

### Additive CLI (cli.py — append only, not ruff-format-enforced)

- `live-db-provenance-audit --project --work-root [--live-db-path]` → rc 0 (v59 tables present) / 1 (`missing_v59_tables`) / 3 (refusal).
- `live-db-readonly-certification --project --source-package --work-root --context-stamp [--live-db-path]` → rc 0 (`certified_match`) / 1 (other completed decision) / 3 (refusal).
- `guarded-db-operator-run`: adds `--allow-certified-live-db` + `--live-db-certification` (rc unchanged: 0/1/3). All existing commands untouched.

## Live-DB read-only guarantee

The live DB is opened solely through `mode=ro` URIs (never created/migrated/projected/written). The
boundary tolerates unavoidable read-only OS metadata (WAL/SHM); the certified invariant is that the
live DB's **content** is never modified. Phase 13 validation confirmed the real live DB's size and
mtime were identical before and after the full run.

## Real-data operator example (documentation only — never executed in tests)

```bash
# 1. Audit (read-only) the live DB.
python -m construction_financial_review.cli live-db-provenance-audit \
  --project tropical --work-root "<non-live evidence root>"

# 2. Certify (read-only) the live DB against a fresh temp projection.
python -m construction_financial_review.cli live-db-readonly-certification \
  --project tropical \
  --source-package "<Tropical data root>/twn_cost_forecast_json_package" \
  --work-root "<non-live evidence root>" --context-stamp "<operator stamp>"

# 3. Guarded operator run with certified-equivalence opt-in (executes against a fresh temp DB).
python -m construction_financial_review.cli guarded-db-operator-run \
  --project tropical \
  --source-package "<Tropical data root>/twn_cost_forecast_json_package" \
  --work-root "<non-live operator root>" --context-stamp "<operator stamp>" \
  --db-path "<live DB path>" --allow-certified-live-db \
  --live-db-certification "<certification report from step 2>"
```

## Test strategy

`tests/test_forecast_live_db_certification_phase13.py` (29 tests). A synthetic "live" DB = a temp DB
(migrate +/- project), WAL-checkpointed (TRUNCATE) so read-only reads cannot drift its content, with
`is_live_db_path` monkeypatched so it is treated as the live DB. Covers: audit (read-only inspection,
migration rows, table presence, counts, schema_only vs populated_tropical, refusals, content-unchanged,
determinism); certification (certified_match, schema_only, stale_or_mismatch via a mutated source,
counts+digests, determinism, refusals, live-DB content-unchanged); guarded opt-in (refuse live without
flag / without cert / wrong decision / wrong source / wrong live DB; allow when all match → manifest
`live_db.used_for_execution == false`, temp DB under the operator root, live DB content unchanged);
CLI rc 0/1/3. Everything runs under `tmp_path`; the real live DB is never used. `build_fixture` is
duplicated per the per-phase test independence convention.

## Consequences

- Production-facing live-DB **eligibility evidence** (audit + certification) with zero live-DB mutation
  risk, and a guarded opt-in that records live-DB certification while still executing on the proven
  non-live temp path.
- No schema change; `LATEST_SCHEMA_VERSION` stays **59**; lifecycle table count stays **387**; no v60;
  no `hb_assistant` source change.

## Deferred (unchanged by Phase 13)

- **True read-only live execution** (a `mode=ro` Phase 4/9 adapter path) — the next prerequisite for
  live-DB execution rather than certified-equivalence.
- Production DB-backed default enablement; DB-backed reads/resolution as default.
- Global latest-glob/config-pin/run-state replacement.
- The v58 `forecast_package_manifests` DB resolver.
- Final integrated forecast CSV DB generation; the −$3.42M reconciliation.
- Intelligence/comprehensive/model-backed parity.
- Full DB domain migration beyond the v59 source domain; owner/Procore/control/staffing/schedule DB reads.
- Class-based generator cleanup.
