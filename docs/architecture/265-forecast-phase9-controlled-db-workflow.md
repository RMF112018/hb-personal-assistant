# ADR 265 — Forecast Phase 9: controlled DB-backed context→analysis workflow

- **Status:** Accepted
- **Date:** 2026-06-18
- **Phase:** Forecast JSON/JSONL → SQLite transition, Phase 9
- **Builds on:** ADR 258 (Phase 2 lineage), ADR 259 (Phase 3 v59 source-domain read parity), ADR 260 (Phase 4 DB read adapter), ADR 261 (Phase 5 context-generator parameterization), ADR 262 (Phase 6 controlled context generation), ADR 263 (Phase 7 controlled analysis parity), ADR 264 (Phase 8 package-resolution hardening); v58 (PR #29), lifecycle contract (PR #30), Phases 2–8 (PRs #31–#37, Phase 8 merge `e2bca91`).

## Context

Phases 6–8 delivered three proven, default-off, controlled building blocks: a context-generation
runner (file- or DB-backed), an analysis runner (hard-pinned to one explicit context package), and
an explicit package-resolution + deterministic chain-manifest layer. But an operator still had to
invoke those **three steps by hand** and thread paths/stamps between them; there was no single,
auditable operation to run — and no built-in way to **compare** a file-backed run against a
DB-backed run.

Phase 9 adds the first **workflow command layer**: one explicit operation that runs the controlled
chain end to end and emits an operator audit report, plus a parity mode that runs both backings and
proves they agree. Package-resolution hardening (Phase 8) alone is **not** enough — it gives typed
identity for packages that already exist, but does not orchestrate their creation, sequencing, or
comparison.

It is **not** a production DB cutover, not final/integrated CSV generation, not a domain migration,
and not the deferred v58 `forecast_package_manifests` DB resolver. It changes **no** production
default.

## Decision

### New orchestration layer (CFR-only)

New package `construction_financial_review/workflows/` with
`controlled_db_context_analysis.py`. This is the orchestration layer **above** `context/`
(Phase 6), `analysis/` (Phase 7), and `common/` (Phase 8). It imports those three building blocks
and **never imports `hb_assistant` directly** — the only DB touchpoint is the Phase 6 runner's
existing lazy, fail-closed DB branch. The module was placed in a new `workflows/` package, not in
`common/`, because `common/` is the leaf layer and must not depend on `context/`/`analysis/`.

Primary API:

- `run_controlled_context_analysis_workflow(*, data_root, work_root, context_stamp, mode, db_path=None, project_key="tropical", run_id=None, chain_manifest_name=...) -> dict` — runs one `file` or `db` mode chain.
- `run_controlled_context_analysis_parity(*, data_root, work_root, context_stamp, db_path, project_key="tropical") -> dict` — runs both and compares.

### Single-run behavior (orchestration only)

For one run the workflow performs exactly:

1. **Phase 6** controlled context generation into the explicit
   `<work_root>/<mode>/forecast_context_package_tropical_<context_stamp>` (file-backed by default;
   DB-backed only when `mode="db"`, gated by the Phase 6 runner's own DB-path/live-DB validation).
2. **Phase 7** controlled analysis generation hard-pinned to that context package (the analysis
   package lands beside it under `<work_root>/<mode>/`).
3. **Phase 8** explicit resolution of both produced packages into `ForecastPackageRef`s.
4. **Phase 8** deterministic chain manifest written to `<work_root>/<mode>/<chain_manifest_name>`.
5. A deterministic operator report at `<work_root>/<mode>/controlled_workflow_report.json`.

It does **not** run intelligence, comprehensive, probability, monthly, model-controls, staffing,
final-integrated forecast, or any CSV generation. There is no LLM/model-backed step.

### Explicit work roots; no live-root writes; no latest-glob

Everything is written under the explicit `work_root` (`<work_root>/file` or `<work_root>/db`).
Nothing is ever written under the live Synology forecast root, and no recency-based (latest-glob)
discovery is used anywhere — the chain is resolved entirely from the explicit produced paths.

### Fail-closed preflight (before any output)

`run_controlled_context_analysis_workflow` raises `ControlledWorkflowError` — **before** Phase 9
creates its `<work_root>/<mode>` directory or invokes any downstream runner — on: non-tropical
project key; missing/non-directory `data_root`; missing `work_root` or a `work_root` at/under the
live forecast root; empty `context_stamp`; invalid `mode`; `db` mode without `db_path`; `file` mode
**with** a `db_path` (ambiguous operator intent — rejected by design); or a mode subdir that already
holds the context/analysis package for this stamp. (Phase 6/7 creating package directories during
normal execution is expected; the rule is only that Phase 9's *own* refusals fire first.) The
Phase 6/7 runners' own fail-closed errors (unsafe/missing DB path, live root, missing v59 rows,
pre-existing analysis package) propagate unchanged.

The `file`-mode-rejects-`db_path` contract is the explicit choice for test item #11: a `db_path` in
file mode signals confused intent, so it fails closed rather than being silently ignored.

### Deterministic report (no wall-clock added by Phase 9)

The operator report is written with sorted keys, indentation, and a trailing newline; Phase 9 adds
**no** wall-clock field of its own. Keys: `schema_version` (1), `project_key`, `mode`, `data_root`,
`work_root`, `context_stamp`, `db_backed`, `db_path` (or `null`), `context_package`,
`context_package_stamp`, `analysis_package`, `analysis_package_stamp`, `chain_manifest`,
`safety_checks`, `status`. The only volatile content is the **generator-assigned analysis stamp**
embedded in `analysis_package` / the chain manifest — a known downstream volatile value, treated as
such for test normalization only.

### Parity mode (narrow)

`run_controlled_context_analysis_parity` runs `file` under `<work_root>/file` and `db` under
`<work_root>/db` (separate roots, so Phase 7's "analysis already exists" guard never trips across
modes), then compares **only**:

- context package outputs (Phase 5/7 normalization: volatile keys, `sha256`/`size_bytes`, package
  root path + package dir name);
- analysis package outputs (same normalization);
- the two chain manifests (after root-path + analysis-stamp normalization).

Downstream comprehensive/final/integrated outputs are **never** compared (none are produced). It
emits a deterministic parity report (`controlled_workflow_parity_report.json`) with both per-mode
report paths, the three comparison results, the normalized-field list, and `status` ∈ {`pass`,
`fail`}. The comparison helpers are a small CFR-only stdlib leaf inside the workflow module — not a
broad comparison framework.

### Additive CLI command

`controlled-context-analysis --project tropical --data-root <src> --work-root <work> --context-stamp <stamp> --mode {file,db,parity} [--db-path <temp.sqlite>]` runs the workflow/parity, prints clean
JSON (the operator/parity report) to stdout, and returns rc 3 on any controlled refusal. The
existing `context-generate`, `final-forecast-generate`, `package-chain-manifest`, `run-context`,
`run-analysis`, and all other commands are **unchanged**.

### Runner/resolver integration — non-breaking

The Phase 6/7 runner return dicts and the Phase 8 resolver API are **unchanged**. Phase 9 consumes
their existing `output_package` paths and Phase 8 public helpers (`resolve_explicit_package`,
`build_package_chain`, `write_package_chain_manifest`) — it does not re-implement manifest I/O.

## v58 `forecast_package_manifests` DB resolution — STILL DEFERRED

Per ADR 264, the read-only resolver against the v58 `forecast_package_manifests` table remains
deferred and is **not** implemented here. Phase 9 emits package **directories** + a deterministic
chain manifest; it has no consumer that selects chains from persisted package-manifest DB rows. No
`hb_assistant` reader, schema, DB resolver, or package-manifest selection logic is added.

## Live safety

No Phase 9 test writes under the live Synology root or touches the live/default DB; all packages,
manifests, and reports are under `tmp_path`, and DB-mode/parity tests use a temp SQLite DB only. The
workflow refuses any `work_root` at/under the live root, and DB safety is enforced by the Phase 6
runner.

## Test strategy

`tests/test_forecast_controlled_workflow_phase9.py` (mirrors the Phase 6/8 fixture/DB-projection
pattern; `build_fixture`/`_wj`/`_wjson`/`_project_db` are duplicated, not imported): file-mode
success; DB-mode success (temp v59 DB); deterministic chain manifest (re-resolve + re-write →
byte-identical); deterministic sorted-key report; report key coverage; the full fail-closed guard
matrix (bad project, missing data root, live-root work root via monkeypatched `_LIVE_ROOT`, invalid
mode, db-without-db-path, file-with-db-path, empty stamp); parity success (file vs DB context +
analysis + chain all match) + parity report; CLI file/db/parity success + CLI db-without-db-path
refusal; and existing-command route preservation. All outputs under `tmp_path`; temp SQLite only.

## Scope / deferrals

Production DB-backed default enablement; global latest-glob/config-pin/run-state replacement; final
integrated forecast CSV DB generation; intelligence/comprehensive/model-backed parity; full DB
domain migration; owner/Procore/control/staffing/schedule DB reads; the v58 package-manifest DB
resolver; the −$3.42M reconciliation; class-based generator cleanup. Phase 10 is not started.

## Consequences

- **No schema change** (`LATEST_SCHEMA_VERSION` stays 59; no v60). **No lifecycle-contract change** (`table_count` stays 387). **No `hb_assistant` source change** (Phase 9 is entirely CFR-only).
- An operator can now run the controlled file-backed, DB-backed, or parity context→analysis chain in **one** explicit, auditable operation under a temp/work root, getting package refs, a deterministic chain manifest, and a structured report — without relying on filesystem recency and without changing any production default.
- Changed surface is additive: one new CFR `workflows/` package (two modules), one new CFR CLI subcommand, one new test module, and this ADR.
- Live DB untouched (still v58, no v59 domain tables); no live-root output written.
