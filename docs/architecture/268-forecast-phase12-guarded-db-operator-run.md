# ADR 268 — Forecast Phase 12: controlled guarded DB operator-run package

- **Status:** Accepted
- **Date:** 2026-06-18
- **Phase:** Forecast JSON/JSONL → SQLite transition, Phase 12
- **Builds on:** ADR 258–267 (Phases 2–11); v58 (PR #29), lifecycle contract (PR #30), Phases 2–11 (PRs #31–#40, Phase 11 merge `f1a2fdf`).

## Context

Phase 11 added the temp-DB **readiness rehearsal**: a single controlled command goes from explicit
Tropical source data → non-live temp v59 DB (migrate + project) → Phase 10 readiness gate →
deterministic rehearsal report. But a *passing rehearsal is only evidence*. For an operator to
actually use the DB-backed context→analysis result, something must name **which** DB-backed
artifacts are approved, and bind them to the full safety/provenance chain. Phase 12 closes that gap
with an **operator handoff**:

    explicit Tropical source package -> Phase 11 rehearsal -> validate the nested Phase 10 readiness +
    Phase 9 DB-mode artifacts (Phase 8 resolution) -> deterministic guarded DB operator-run manifest.

### Why the rehearsal alone is not an operator handoff

The rehearsal report records a `passed`/`failed` decision and the path of the Phase 10 report, but it
does not (a) extract the approved DB-backed context/analysis/chain artifacts, (b) re-validate that
those artifacts exist, sit under the explicit work root, are not under the live root, and resolve
cleanly via the Phase 8 explicit package helpers, or (c) certify the DB-mode semantics
(`mode == "db"`, `db_backed is True`) and that the chain manifest matches the DB-mode report. Phase 12
performs that validation and emits one auditable artifact an operator can act on.

Phase 12 is still **not** a production default flip: no live/default DB writes, no DB-backed reads or
package resolution as default, no removal of file-backed paths, no global latest-glob/config-pin/
run-state replacement, no final integrated CSV from DB, no model-backed/intelligence/comprehensive/
probability/monthly/model-controls/LLM workflows, and no new domain migration beyond the existing
v59 source-domain projection.

## Decision

### New CFR-only operator-run module (orchestration reuse)

New `workflows/guarded_db_operator_run.py`, above the Phase 11 rehearsal. It **reuses** Phase 11
(`run_temp_db_readiness_rehearsal`), the Phase 10/Phase 9 report OUTPUTS (read back from disk), and
the Phase 8 package-resolution helpers (`read_package_chain_manifest`, `resolve_explicit_package`).
It reimplements none of temp-DB prep, projection, parity, readiness, or package resolution. The only
`hb_assistant` touchpoint is a lazy, fail-closed live-DB check on an **explicit** `db_path` (via a
module-ref call so tests monkeypatch it cleanly); Phase 11 enforces the authoritative DB safety again.

API: `run_guarded_db_operator_run(*, source_package, work_root, context_stamp, db_path=None, project_key="tropical") -> dict`.

### Lightweight preflight (fail closed, before any output)

`project_key == "tropical"`; `source_package` exists and is a directory; `work_root` explicit and not
at/under the live Synology root; `context_stamp` nonempty; and, **only when an explicit `db_path` is
given**, it must resolve under the work root and must not be the live/default DB. Deeper temp-DB
reuse / pre-existing-DB / work-root-emptiness checks are **delegated to Phase 11**, whose
`TempDbRehearsalError` is mapped to a Phase 12 controlled refusal.

### Execution + artifact validation

1. Run `run_temp_db_readiness_rehearsal(...)`. `TempDbRehearsalError` → `GuardedDbOperatorRunError`.
2. If the rehearsal does not `pass`, emit a successful operator-run result with `status="not_ready"`,
   `decision="not_ready"`, the rehearsal evidence path, and **no approved artifacts**.
3. If it passes, load the nested **Phase 10 readiness report** (`rehearsal.readiness.report_path`);
   require `decision == "ready_for_guarded_operator_use"`.
4. Load the **Phase 9 DB-mode report** (`phase10.workflow.db_report`).
5. Certify DB-mode semantics: `mode == "db"` and `db_backed is True` where those fields exist.
6. Extract and validate `context_package`, `analysis_package`, `chain_manifest`: each exists, resolves
   **under the work root**, and is **not under the live root**.
7. `read_package_chain_manifest(chain_manifest)` must resolve to the **same** context/analysis package
   paths as the DB-mode report; `resolve_explicit_package(...)` must succeed for both packages.
8. Write the deterministic guarded operator-run manifest under the work root.

### Decision values and CLI rc mapping

- `approved_for_guarded_db_context_analysis_use` / status `ready` / **rc 0** — only when Phase 11
  passed, Phase 10 readiness passed, the Phase 9 DB-mode report is structurally valid, and the Phase 8
  chain/package validation succeeds.
- `not_ready` / status `not_ready` / **rc 1** — only when Phase 11 completes and returns
  failed/not-ready evidence.
- `GuardedDbOperatorRunError` / **rc 3** — unsafe/missing/ambiguous input, OR any
  structural/provenance inconsistency discovered **after** a passing rehearsal (missing nested report,
  decision mismatch, missing DB-mode report, wrong DB-mode semantics, chain mismatch, artifact path
  escape, live-root/live-DB risk).

The fail-closed distinction is deliberate: a `passed` rehearsal already implies the Phase 10 decision
is ready and the DB-mode artifacts exist, so any nested inconsistency afterwards signals a broken or
tampered evidence chain — a **controlled refusal**, not a soft `not_ready`.

### Approved artifact

A DB-backed artifact is *approved* only after the full chain passes: a context/analysis package whose
directory exists under the explicit work root (never under the live root), resolves via the Phase 8
explicit helpers, and is named by a chain manifest that matches the Phase 9 DB-mode report.

### Manifest shape (deterministic: sorted-key JSON, trailing newline, no wall-clock)

```json
{
  "schema_version": 1,
  "project_key": "tropical",
  "status": "ready",
  "decision": "approved_for_guarded_db_context_analysis_use",
  "source_package": "<path>",
  "data_root": "<path>",
  "work_root": "<path>",
  "context_stamp": "<stamp>",
  "temp_db": { "path": "<path>", "schema_version": 59 },
  "evidence": {
    "phase11_rehearsal_report": "<path>",
    "phase10_readiness_report": "<path>",
    "phase9_db_report": "<path>",
    "db_chain_manifest": "<path>"
  },
  "approved_artifacts": {
    "context_package": "<path>",
    "analysis_package": "<path>",
    "chain_manifest": "<path>"
  },
  "source_domain_counts": {
    "forecast_budget_details": 1,
    "forecast_cost_entries": 2,
    "forecast_monthly_actuals_by_budget_code": 2
  },
  "safety": {
    "production_defaults_changed": false,
    "live_db_written": false,
    "live_root_written": false,
    "final_integrated_csv_generated": false
  }
}
```

The `not_ready` manifest omits `approved_artifacts`/`temp_db`/`source_domain_counts` and records only
the rehearsal evidence path and its Phase 11 decision.

### Additive CLI

`guarded-db-operator-run` mirrors `temp-db-readiness-rehearsal`: required `--project`,
`--source-package`, `--work-root`, `--context-stamp`; optional `--db-path` (under work root,
non-live). Workflow chatter is redirected to stderr so stdout is clean machine-readable JSON; rc 0
approved / rc 1 not-ready / rc 3 refusal. All existing commands are unchanged. `cli.py` is **not**
ruff-format-enforced; the change is additive only.

## Real-data operator example (documentation only — never executed in tests)

```bash
python -m construction_financial_review.cli guarded-db-operator-run \
  --project tropical \
  --source-package "<Tropical data root>/twn_cost_forecast_json_package" \
  --work-root "<non-live temp guarded run root>" \
  --context-stamp "<operator-chosen stamp>"
```

## Test strategy

`tests/test_forecast_guarded_db_operator_run_phase12.py` (26 tests). Success / determinism / evidence /
approved-artifact / counts tests run the **real** Phase 11 chain end-to-end (as Phase 11 tests run
real Phase 10). Refusal / corruption / not-ready tests **monkeypatch** the rehearsal to return crafted
evidence (a synthetic on-disk Phase 9/10 + chain tree), exercising Phase 12's own validation in
isolation. `build_fixture`/`_wj`/`_wjson` are duplicated (not imported) per the per-phase test
independence convention. Everything runs under `tmp_path`; no live Synology data, no live DB writes.

## Consequences

- One guarded, auditable operator handoff artifact for the DB-backed context→analysis chain, produced
  only after temp-DB prep, projection, parity, readiness, and rehearsal all pass.
- No schema change; `LATEST_SCHEMA_VERSION` stays **59**; lifecycle table count stays **387**; no v60;
  no `hb_assistant` source change.

## Deferred (unchanged by Phase 12)

- Production DB-backed default enablement; DB-backed reads/resolution as default.
- Global latest-glob/config-pin/run-state replacement.
- The v58 `forecast_package_manifests` DB resolver (writer exists, zero readers).
- Final integrated forecast CSV DB generation; the −$3.42M reconciliation.
- Intelligence/comprehensive/model-backed parity.
- Full DB domain migration beyond the v59 source domain; owner/Procore/control/staffing/schedule DB
  reads.
- Class-based generator cleanup.
