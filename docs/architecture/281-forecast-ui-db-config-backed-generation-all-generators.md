# ADR 281 — Forecast UI: extend DB-config-backed generation to all four generators

- **Status:** Accepted
- **Date:** 2026-06-21
- **Phase:** Forecast CLI→UI product, DB-config-backed generation (all generators)
- **Builds on:** ADR 280 (comprehensive db-config-backed generation), ADR 273–276 (Phase 17–20
  db-config consumer proofs), ADR 272 (v60 config registry), the Phase 3 Run Center.

## Context

ADR 280 productionized the DB-config-backed generation path for the **comprehensive** generator only:
a promoted config snapshot drives comprehensive generation (`config_snapshot_consumed: True`), gated on
materialization fidelity. The other three generators — **model_controls**, **monthly**, **probability**
— were already *proven* to produce file↔DB parity when run with `CFR_CONFIG_ROOT = <materialized
snapshot>` (Phases 17–19), but in the controlled generation path they still read file config only. So
promoting a config edit changed the comprehensive forecast but not the model-controls / monthly /
probability packages it depends on. This phase wires those three into the same gated path, in one PR,
exposed via the CFR CLI and a UI generator-kind selector.

## Decision

The materialize-read-only → fidelity-gate → quiescence-preflight → `CFR_CONFIG_ROOT` bridge →
redacted-report machinery is **snapshot-level and generator-agnostic**. Only the generator invocation,
predecessor-package requirements, consumed-config accounting, and a couple of kind-specific guards
differ. So we factor one shared gated core + a per-kind descriptor registry, rather than four
near-identical workflow files.

### Shared core + descriptor registry (CFR)

New `workflows/forecast_db_config_backed_core.py` holds `run_db_config_backed_generation(*, descriptor,
…)` — the exact step sequence from ADR 280, parameterized by a frozen `GeneratorDescriptor` that
supplies, per kind:

- `run` — the generator's deterministic `_run_<gen>` helper from its **proof module** (single source of
  truth; the same helpers Phases 17–20 already test). Probability binds its determinism knobs
  (`runs`/`seed`/`forecast_start_month`) in a closure.
- `required_globs` / `optional_globs` — predecessor packages to pre-check (model_controls declares
  **none** — its generator self-discovers; we don't invent a guard the proof doesn't have).
- `consumed_domains` — a **callable**, not a constant list, because accounting differs: comprehensive
  maps 3 named domains, monthly prefix-aggregates 4, probability adds the owner-SOV crosswalk,
  model_controls filters the `forecast_model_controls` files.
- `reads_materialized` — comprehensive resolves its control paths through the bridge (computed while
  `CFR_CONFIG_ROOT` is set); the others verify each consumed file exists under the materialized root.
- `cost_frequency_guard` (comprehensive only) and `catch_system_exit` (monthly only).
- `safety_run_key` — the kind-appropriate `safety` run flag.

`get_descriptor(kind, …)` resolves the four kinds (else a coded `unsupported_generator_kind` refusal).
Proof modules are imported lazily per factory.

`workflows/forecast_db_config_backed_generation.py` keeps `run_forecast_db_config_backed_generation`
(comprehensive) **byte-for-byte** by delegating to the core with the comprehensive descriptor, and
**re-exports** the symbols the existing tests pin (`STATUS_*`, `REASON_*`, `DB_BACKED_SUBDIR`, `cr`,
the error class). A new `run_forecast_db_config_backed_generation_for_kind(generator_kind=…, …)` is the
entry point for the CLI and service.

### Kind-specific safety

- **Monthly** integrations call `assert_integration_safe()`, which raises `SystemExit` when unsafe. The
  core wraps the monthly run in `except SystemExit → ForecastDbConfigGenerationError(generator_refused)`
  **inside** the `CFR_CONFIG_ROOT` restore `try/finally` — an unsafe integration becomes a controlled
  refusal, never a process kill or a leaked env var.
- **Probability** runs the byte-deterministic Monte-Carlo core with a fixed `runs`/`seed`/`run_stamp`;
  the descriptor defaults them and the service never varies them.
- **Comprehensive** keeps the cost-frequency guard (refuse before generating, so it never writes
  `forecast_cost_frequency` into the read-only data root); this guard is comprehensive-only.

### CLI + Run Center surface

CLI `forecast-db-config-backed-generate` gains `--generator-kind`
(`comprehensive` [default] / `model_controls` / `monthly` / `probability`) plus probability-only
`--runs`/`--seed`/`--forecast-start-month`; omitting `--generator-kind` is the unchanged comprehensive
path (rc 0/1/3 preserved). One shared `HB_FORECAST_DB_CONFIG_RUN_ENABLED` opt-in still gates all four
kinds (no per-kind toggles; `surfaces_ready` unchanged). The POST route `/api/forecast/runs/db-config`
accepts an optional JSON body `{"generator_kind": …}` (absent → comprehensive, back-compat), validates
the kind (400 `forecast_db_config_run_bad_kind` on invalid), and stays singular — no path explosion, no
`{run_id}` ambiguity, OpenAPI route allowlist unchanged. The service persists `generator_kind`; the DTO
builds a per-kind friendly label and carries `kind`. The frontend replaces the single button with a
four-option generator-kind selector.

## Consequences

- Promoting a config snapshot now drives any of the four forecast generators from the live config,
  fidelity-gated, with `config_snapshot_consumed: True`.
- Live config DB read-only throughout; writes confined to the isolated runs-root; no DB/schema/migrator
  change (live DB stays v61). Structural redaction holds — `kind` is a bare enum and the new labels are
  friendly text; every UI payload still passes `find_redaction_leaks == []`.
- Back-compat is load-bearing and verified: the comprehensive public signature, the `genwf.*`
  re-exports, the CLI `command` literal, the default-comprehensive POST, and the comprehensive label
  string are all unchanged (the prior 9 comprehensive tests pass untouched).
- Per-kind generation + fidelity/quiescence/predecessor + monthly-SystemExit refusals are covered by a
  new CFR kinds test reusing the Phase 17–20 reduced fixtures; CFR full suite 565 green.
- A real end-to-end generation against live data (beyond the read-only materialize smoke) remains a
  separate authorized operation.
