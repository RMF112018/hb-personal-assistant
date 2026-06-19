# ADR 271 — Forecast Phase 15: controlled DB-certified final forecast output

- **Status:** Accepted
- **Date:** 2026-06-19
- **Phase:** Forecast JSON/JSONL → SQLite transition, Phase 15
- **Builds on:** ADR 258–270 (Phases 2–14); v58 (PR #29), lifecycle contract (PR #30), Phases 2–14 (PRs #31–#43, Phase 14 merge `29bd29f1`).

## Context

Phase 14 ran for real against the live/default DB: it backed up the live DB, projected the Tropical
source-domain rows in one transaction, and reran Phase 13 certification → `certified_match`. The live
DB now holds `forecast_budget_details=127`, `forecast_cost_entries=6324`,
`forecast_monthly_actuals_by_budget_code=1081` for `project_key='tropical'`, with a guarded operator
proof (`approved_for_guarded_db_context_analysis_use`, `live_db.used_for_execution==false`,
`equivalent_to_temp_db==true`).

**Phase 15** turns that certification into an **eligibility gate** and runs the existing controlled,
deterministic final-output chain under an explicit work root, labelling the result a *DB-certified
final forecast output*:

    Phase 14 certified evidence (gate) -> rerun Phase 13 read-only certification (require
    certified_match, counts consistent with Phase 14) -> Phase 12 guarded operator run under
    <work_root>/guarded (a fresh NON-LIVE temp v59 DB drives Phase 11->10->9; the live DB is never
    executed against) -> copy the approved DB-certified analysis package under <work_root>/final_output/
    -> deterministic Phase 15 report + summary.

### Repo-truth: the in-scope generator emits no integrated CSV

The only in-scope deterministic final generator is the **Phase 7 analysis package**
(`analysis/final_forecast_runner.py::run_final_forecast_generation` wrapping
`generate_forecast_analysis_package.py`): pure-deterministic (refuses `deterministic=False`, no
LLM/Ollama), never mutates source, and writes JSONL/JSON/Markdown with per-file `row_count` + `sha256`
in `manifest.json`. It does **not** emit the true integrated CSV — that is produced downstream by
`forecast_comprehensive` / `forecast_monthly` / `forecast_probability`, all out of scope for Phase 15.
Per repo-truth and the operator decision, Phase 15 therefore does **not** invent a rewrite and does
**not** synthesize a flattened analysis CSV: `generate_final_csv` is a **controlled refusal**.

### Why this is safe and not a cutover

The live DB is opened **read-only only** (certification verification; `mode=ro`). Execution always uses
a fresh non-live temp DB via the reused Phase 12 guarded run — the live DB is never executed against,
migrated, projected, or written. This is **not** a production default cutover: no DB-backed
reads/resolution default, no file-backed path removal, no integrated CSV from DB, no
intelligence/comprehensive/probability/monthly/model-controls/LLM workflows, no Phase 4/9 live read
execution. **Invariants:** no schema change, `LATEST_SCHEMA_VERSION==59`, lifecycle `387`, no
`hb_assistant` source change.

## Decision

### New CFR-only module `workflows/db_certified_final_output.py`

`run_db_certified_final_output(*, phase14_report, source_package, work_root, context_stamp, project_key="tropical", live_db_path=None, require_certified_live_db=True, require_guarded_operator_check=True, generate_final_csv=False, run_id=None) -> dict`.
`DbCertifiedFinalOutputError` (fail closed). Reuses Phase 13 `live_db_certification`
(`run_live_db_readonly_certification`, `_write_json_deterministic`, `_resolve_live_db_path`,
`_is_live_db`, `CERT_MATCH`) and Phase 12 `guarded_db_operator_run` (`run_guarded_db_operator_run`).
`hb_assistant` is only ever touched transitively by those reused workflows (lazily, temp DB only) or by
a lazy live-DB safety check.

> Deviation from the suggested API: `generate_final_csv` defaults to **False** so the conservative rc0
> happy path is the default and matches the CLI `--generate-final-csv` store_true flag; requesting it is
> the documented out-of-scope refusal (rc1).

**Eligibility gates (fail closed → rc3, before any output):** project==tropical; explicit work root not
under the live root and not equal to the source package; nonempty context stamp; source package exists +
named `twn_cost_forecast_json_package` + matches the Phase 14 report; Phase 14 report readable JSON with
`status==ready`, `decision==live_db_source_domain_certified`, and the seven safety flags
(`live_db_written` true; `live_db_migrated`/`live_db_projected_directly`/`production_defaults_changed`/
`final_integrated_csv_generated`/`true_live_execution_used` false; `projected_via_temp_db` true); Phase
14 post-write certification `certified_match` with each table `match==true` and `live_rows==temp_rows`
(embedded + on-disk); Phase 14 guarded proof `ready`/approved with
`live_db.certified`/`certification_decision==certified_match`/`equivalent_to_temp_db` true and
`used_for_execution` false; backup file present with sha256 matching the report; a provided
`live_db_path` matching the report and resolving to the live/default DB.

**Rerun certification (required for a real run).** Reruns Phase 13
`run_live_db_readonly_certification` under `<work_root>/current_certification` (live DB read-only only)
and requires `certified_match`. Each table's rerun `live_rows` must equal the Phase 14 post-write
certified `live_rows` — a **no-drift consistency gate** that inherently re-confirms the real **127 /
6324 / 1081** baseline without hardcoding it (synthetic tests use their own counts). Drift → rc3.

**Controlled chain.** Calls Phase 12 `run_guarded_db_operator_run` under `<work_root>/guarded` with
`db_path=<live>`, `allow_certified_live_db=True`, `live_db_certification=<rerun cert report>`. The
guarded run, given a live `db_path` + a `certified_match` cert, builds and executes a **fresh non-live
temp DB** (Phase 11→10→9 db-mode) and emits approved `context_package` / `analysis_package` /
`chain_manifest` — the live DB is recorded as evidence only (`used_for_execution=false`).

**Final output assembly.** The approved Phase 7 analysis package is the DB-certified final forecast
deliverable. Phase 15 deterministically copies it to `<work_root>/final_output/<package>/`, records
per-file sha256 and per-`.jsonl` row counts (line counts — independent of the analysis manifest's
internal shape), and emits `<work_root>/db_certified_final_output_report.json` (sorted-key, no
wall-clock) + `<work_root>/db_certified_final_output_summary.md`. Success →
`decision=db_certified_final_output_ready` / status `ready` (rc 0). A guarded run that does not approve
is an outcome → `not_ready` (rc 1), not a refusal.

**CSV controlled refusal.** When `generate_final_csv` is requested (after the eligibility + rerun-cert
gates pass), the run records `csv_generation={requested:true, decision:"out_of_scope", blocker:"true
integrated CSV is produced by forecast_comprehensive/monthly/probability, which Phase 15 boundaries
defer"}`, keeps `safety.final_integrated_csv_generated=false`, produces no CSV and no analysis copy, and
returns `not_ready` (rc 1). The CLI JSON carries the exact blocker and does not imply a code failure.

### Additive CLI (cli.py — append only, not ruff-format-enforced)

`db-certified-final-output`: required `--project --phase14-report --source-package --work-root
--context-stamp`; flags `--live-db-path`, `--require-guarded-operator-check` (default on),
`--generate-final-csv`, `--run-id`. JSON to stdout (subprocess/workflow chatter redirected to stderr).
rc 0 (`db_certified_final_output_ready`) / 1 (not-ready, incl. CSV requested) / 3 (controlled refusal).
All existing commands unchanged.

## Real-data operator example (documentation only — never executed in tests)

```bash
python -m construction_financial_review.cli db-certified-final-output \
  --project tropical \
  --phase14-report "<Phase 14 evidence>/live_db_source_domain_projection_report.json" \
  --source-package "<Tropical data root>/twn_cost_forecast_json_package" \
  --work-root "<non-live work root>" --context-stamp "<operator stamp>"
```

The real DB-certified final-output run is a separate operational execution requiring Bobby's explicit
go-ahead; it was not run during implementation/tests (synthetic evidence + a synthetic live DB only).

## Test strategy

`tests/test_forecast_db_certified_final_output_phase15.py` (28 tests). Synthetic Phase 14 evidence
(hand-written report + backup + sub-reports) drives the fast gate-refusal cases (missing/malformed
report; wrong decision; post-write cert not match; table `match=false`; guarded
`used_for_execution`/`equivalent_to_temp_db`; missing backup; backup sha mismatch; mismatched
source/live path; unsafe work root; rerun-cert mismatch; count drift). The controlled-generation cases
monkeypatch the reused Phase 12 guarded run + Phase 13 rerun cert to assert the analysis-package copy,
per-file sha256, per-JSONL row counts, outputs-under-work-root, deterministic report, safety flags,
unchanged live DB, unmutated source package, CSV controlled refusal, and CLI rc 0/1/3. One real
end-to-end test builds genuine Phase 14 evidence against a synthetic "live" DB (migrated temp DB,
`is_live_db_path` monkeypatched) and runs the real Phase 15 chain (real rerun cert + real guarded run)
through to the copied analysis package. Synthetic only; the real live DB is never touched.

## Consequences

- A safe, gated, reversible-by-construction path to generate the DB-certified final forecast (analysis)
  package from the Phase-14-certified live source-domain DB, tied to that certification by a rerun
  read-only certification and the guarded operator chain — without ever executing against the live DB.
- No schema change; `LATEST_SCHEMA_VERSION` stays **59**; lifecycle table count stays **387**; no v60;
  no `hb_assistant` source change; no production default flipped.

## Deferred (unchanged by Phase 15)

- Production DB-backed default cutover; DB-backed reads/resolution as default.
- True read-only live execution (a `mode=ro` Phase 4/9 adapter path).
- The true final integrated CSV from DB and the −$3.42M reconciliation. A future phase may add either a
  separate, clearly named `db-certified-analysis-csv` export, or a formally widened integrated-CSV phase
  that brings `forecast_comprehensive/monthly/probability` back into scope.
- v58 `forecast_package_manifests` DB resolver.
- Intelligence/comprehensive/model-backed parity.
- Broader domain DB reads (owner/Procore/control/staffing/schedule).
- Phase 16 and beyond.
