# ADR 264 — Forecast Phase 8: controlled package-resolution hardening

- **Status:** Accepted
- **Date:** 2026-06-18
- **Phase:** Forecast JSON/JSONL → SQLite transition, Phase 8
- **Builds on:** ADR 258 (Phase 2 lineage), ADR 259 (Phase 3 v59 source-domain read parity), ADR 260 (Phase 4 DB read adapter), ADR 261 (Phase 5 context-generator parameterization), ADR 262 (Phase 6 controlled context generation), ADR 263 (Phase 7 controlled analysis parity); v58 (PR #29), lifecycle contract (PR #30), Phases 2–7 (PRs #31–#36, Phase 7 merge `e10db1c5`).

## Context

By Phase 7 the controlled context→analysis chain already AVOIDS latest-glob inside the controlled
paths (the Phase 6 context runner takes an explicit `out_dir`; the Phase 7 analysis runner
hard-pins its upstream context via `CFR_CONTEXT_STAMP`). What was missing is a **typed, validated,
serializable package-identity layer**: controlled packages were passed around as bare `Path`s with
ad-hoc name parsing, and there was no first-class way to record/select a context→analysis chain by
**explicit identity** rather than filesystem recency.

Phase 8 adds that layer so a controlled workflow (and a later phase) can resolve and record the
chain by explicit reference/manifest, never by recency — while preserving every production default.
It is **not** a DB cutover, not final CSV generation, not a domain migration.

## Decision

### Explicit package refs + chain manifest (CFR-only, leaf module)

New `common/package_resolution.py` (stdlib only; no `hb_assistant`, no DB, no schema):

- `@dataclass(frozen=True) ForecastPackageRef(project_key, package_kind, package_path, stamp, source="explicit")` — a validated identity for one controlled package directory.
- `@dataclass(frozen=True) ForecastPackageChain(project_key, data_root, packages: dict[str, ForecastPackageRef])` — the context→analysis chain keyed by `package_kind`.
- `resolve_explicit_package(*, package_kind, package_path, project_key="tropical", live_root=None) -> ForecastPackageRef` — validates an explicit directory and returns its ref.
- `package_stamp_from_name(...)`, `validate_package_ref(...)`, `build_package_chain(...)`.
- `write_package_chain_manifest(...)` / `read_package_chain_manifest(...)` — deterministic JSON round-trip.

Supported `package_kind`s: `context` and `analysis` only.

### Controlled-path no-latest-glob policy

The resolver resolves **only** explicit package paths + manifest content. It performs **no**
recency-based discovery. Existing production latest-glob / config-pin / run-state behavior in
`common/lineage.py` and `common/run_lineage.py` is **unchanged and outside** the Phase 8 path. The
resolver is **mode-agnostic**: a context package built file-backed or DB-backed (Phase 6) has
identical on-disk structure, so resolution is purely structure/path based — no DB needed, and no
re-test of Phase 6/7 DB parity is required here.

### Fail-closed validation (no warnings, no soft fallback)

`resolve_explicit_package` raises `PackageResolutionError` on: wrong project key (only `tropical`);
unsupported `package_kind`; missing path; non-directory path; wrong name prefix
(`forecast_context_package_tropical_<stamp>` / `forecast_analysis_package_tropical_<stamp>`); empty
stamp; any missing required member; or a path at/under the live Synology root. Required members
(repo truth): context = `manifest.json`, `validation_report.json`, `canonical/`, `summaries/`;
analysis = `manifest.json`, `validation_report.json`, `forecast_recommendations_by_budget_code.jsonl`.

The live-root check (`_LIVE_ROOT`) is a **controlled-safety guard** that mirrors the generators'
default Synology root — NOT an authoritative environment resolver. It is a module-level constant
that tests monkeypatch; callers may also inject `live_root`.

### Deterministic chain manifest

`schema_version: 1`, written with sorted keys, **no wall-clock timestamp**, trailing newline. It
round-trips back to an equivalent `ForecastPackageChain` and preserves the context and analysis
refs exactly (two writes of the same chain produce byte-identical output).

### Additive CLI command

`package-chain-manifest --project tropical --context-package <path> --analysis-package <path> --out <path>` resolves both explicit packages (live-root refused), builds the chain, writes the deterministic manifest, prints structured JSON metadata, and returns rc 3 on any invalid input. `context-generate`, `final-forecast-generate`, `run-context`, and `run-analysis` are unchanged.

### Runner integration — non-breaking

The Phase 6/7 runner return dicts are **unchanged**. Integration is by consuming their existing
`output_package` paths and resolving those into refs (exercised by a real file-backed end-to-end
test). No latest-glob is introduced; no default changes.

## v58 `forecast_package_manifests` DB resolution — DEFERRED

A read-only resolver against the v58 `forecast_package_manifests` table was considered and
**deferred** (decided with the operator):

- The table has a Phase 2 writer/projection path (`repository.upsert_package_manifest` via `projection_engine.apply_plan`) but **zero readers** anywhere, and is `operational_empty_expected`.
- The controlled Phase 6/7 workflow emits package **directories**, not package-manifest DB rows — so a DB resolver would have **no controlled-chain consumer** yet.
- Adding it now would create an unused reader and expand Phase 8 into `hb_assistant` source changes and DB round-trip tests, contrary to the no-schema / no-hb_assistant-change scope.

It becomes appropriate once a later phase has a real consumer that selects package chains from
persisted run/package metadata rather than from a freshly generated controlled chain manifest.

## Live safety

No Phase 8 test writes under the live Synology root or touches the live DB; all packages and
manifests are under `tmp_path`. The resolver refuses any package path at/under the live root.

## Test strategy

`tests/test_forecast_package_resolution_phase8.py` (CFR-only; imports no `hb_assistant`): fast
structural-stub tests cover the full guard matrix (resolve valid context/analysis; missing path;
non-directory; bad prefix; wrong project key; unsupported kind; missing member; live-root refusal;
stamp parsing; manifest round-trip + determinism; bad schema_version; CLI write/refuse-invalid/
refuse-live-root; existing-command routing). One real **file-backed** integration test runs the
Phase 6 context runner + Phase 7 analysis runner and resolves their actual outputs — validating the
resolver's required-member lists against real generator output (DB-backed context is identical
structure, so no DB test is added).

## Scope / deferrals

Production DB-backed default enablement; global latest-glob/config-pin/run-state replacement; final
integrated forecast CSV DB generation; intelligence/comprehensive/model-backed parity; full DB
domain migration; owner/Procore/control/staffing/schedule DB reads; the v58 package-manifest DB
resolver; the −$3.42M reconciliation; class-based generator cleanup.

## Consequences

- **No schema change** (`LATEST_SCHEMA_VERSION` stays 59; no v60). **No lifecycle-contract change** (`table_count` stays 387). **No `hb_assistant` source change** (Phase 8 is entirely CFR-only).
- Controlled context/analysis workflows can now be represented and resolved by explicit `ForecastPackageRef` / `ForecastPackageChain` and a deterministic chain manifest, independent of filesystem recency, with no production-default change.
- Changed surface is additive: one new CFR leaf module, one new CFR CLI subcommand, one new test module, and this ADR.
- Live DB untouched (still v58, no v59 domain tables); no live-root output written.
