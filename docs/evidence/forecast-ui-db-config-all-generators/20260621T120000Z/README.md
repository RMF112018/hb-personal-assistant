# Evidence — DB-config-backed generation extended to all four generators

**Date:** 2026-06-21 · **ADR:** [281](../../../architecture/281-forecast-ui-db-config-backed-generation-all-generators.md)
· **Branch:** `feature/forecast-ui-db-config-all-generators` · **Base:** origin/main @ 7a1732cc (PR #66)

## What this proves

The DB-config-backed generation path (ADR 280, comprehensive only) is extended to **model_controls**,
**monthly**, and **probability** via one shared gated core + a per-kind `GeneratorDescriptor` registry,
exposed through the CFR CLI (`--generator-kind`) and a UI Run Center generator-kind selector. A promoted
config snapshot can now drive any of the four forecast generators, fidelity-gated, with
`config_snapshot_consumed: True`. No DB/schema/migrator change (live DB stays v61). Live config DB
read-only only; writes confined to an isolated work/runs root.

## Files

- `cfr_backcompat_and_kinds_tests.txt` — the 9 existing comprehensive tests (back-compat, untouched) +
  the new 9 kinds tests (per-kind generate consuming DB config; fidelity / missing-predecessor /
  monthly-SystemExit→refusal / unsupported-kind refusals).
- `cfr_full_suite.txt` — full CFR suite: **565 passed** (no regression).
- `hb_focused_tests.txt` — db-config routes/service (incl. new kind-threading, default-comprehensive,
  bad-kind 400, redaction) + the three lockstep tests (surfaces_ready dict, OpenAPI route allowlist,
  `set(roots)`) — all green and **unchanged in shape** (one shared toggle, singular route).
- `frontend_proof.txt` — ForecastRunCenterPage tests (4/4, incl. the 4-option selector → API kind
  threading), `tsc --noEmit` clean, full vitest (only the 5 pre-existing `SettingsPage.test.tsx`
  failures, unrelated).
- `db_schema_version.txt` — `LATEST_SCHEMA_VERSION = 61` (unchanged).
- `git_state.txt` — scoped changed + new files (no migrator/procore/evidence-churn staged).

## Key invariants

- **Materialization fidelity, not output parity** (per ADR 280) — unchanged and shared across all kinds.
- **Back-compat load-bearing & verified:** comprehensive public signature, `genwf.*` re-exports, CLI
  `command` literal, default-comprehensive POST, and the comprehensive label string are unchanged.
- **Per-kind safety:** monthly `SystemExit` (unsafe integration) → controlled refusal inside the
  `CFR_CONFIG_ROOT` restore; probability fixed `runs`/`seed`/`run_stamp`; comprehensive-only
  cost-frequency guard; model_controls has no invented predecessor guard.
- **Redaction:** `kind` is a bare enum; new labels are friendly text; UI payloads pass
  `find_redaction_leaks == []`.

## Not covered here (deliberately deferred)

A real end-to-end generation against the live data root for the new kinds (beyond the read-only
materialize smoke proven for comprehensive in ADR 280) is a separate authorized operation.
