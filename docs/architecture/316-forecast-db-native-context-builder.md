# 316 — Forecast generation: package-free DB-native context builder

- Status: accepted
- Date: 2026-06-25
- Phase: Forecast Run Center remediation — Phase D (CFR package-free context builder)
- Related: ADR 315 (DB-native source snapshot), ADR 314 (DB-native contract & routing boundary),
  ADR 313 (DB-native boundary, fail-closed)

## Context

The CFR context layer (`context/generate_forecast_context_package.py`) is **package-coupled**: it
reads 16 source files under hard-coded `TWN_DIR`/`OWNER_DIR`/`PROCORE_DIR` (`SRC_FILES`, default root a
Synology TWN path) and **writes a ~33-file context-package directory**. Phase D adds a **package-free
context builder** that consumes the Phase C DB-native source snapshot (`snapshot.public()`) and
produces a **typed, in-memory context object** — not a package directory — beside the untouched legacy
builder.

## Decision

Add `context/db_native_context_builder.py` (pure CFR; **imports no `hb_assistant`**; references no
`SRC_FILES`/`TWN_DIR`/`OWNER_DIR`/`PROCORE_DIR`/`_DEFAULT_DATA_ROOT`):

- `DbNativeContextInput` — plain, path-free input derived from `snapshot.public()`
  (`context_input_from_snapshot_public`). Optional `owner_line_items`/`procore_line_items` exist for
  forward-compatibility (Phase E) but are not derived now.
- `build_db_native_context(source) -> DbNativeForecastContext`:
  - **Fail closed only on required basis** — raises `DbNativeContextError("forecast_context_<reason>")`
    (curated, coded, path-free) when `no_project_identity`/`no_financial_basis` is a blocker or all
    three financial families are empty. Missing optional families never raise.
  - Derives the **financial spine** deterministically (Decimal money; sorted by `budget_code_key`):
    `budget_codes`, per-code `budget_code_context` (budget amounts + actuals + monthly rollup;
    owner/Procore/commitment blocks `available=false`), `project_totals`, a `data_quality`/gap
    register, `provenance` row counts, and a `conclusion`.
  - `DbNativeForecastContext.public()` is the redaction-safe contract: project identity, forecast
    window, readiness/maturity summary, budget codes, per-code financial context, project totals,
    optional-source availability, data-quality/gap register, provenance, conclusion. No local paths,
    package names, package directories, `raw_json`, `source_path`, raw exceptions, payloads, or secrets.
- **This is not byte- or full-semantic parity** with the legacy package. The owner/Procore/owner-
  crosswalk families are **not yet DB-native input rows**; they are reported as `available=false` +
  coded `owner_pay_app_source_unavailable` / `procore_pay_app_source_unavailable` /
  `owner_crosswalk_unavailable` warnings. The builder does **not** wire into the analysis layer.

The legacy `build_context_package` / `ContextPackageConfig` / `_apply_config` / `_reset_state` /
`SRC_FILES` are untouched; the new builder sits beside them.

## Legacy context-package output classification (old vs new)

| Legacy output | Classification | DB-native Phase D |
|---|---|---|
| `summaries/budget_code_forecast_context.jsonl` | required analytical input | financial portion produced in-memory (`budget_code_context`); owner/Procore blocks `available=false` |
| `canonical/budget_codes.jsonl` | required analytical input | produced (`budget_codes`) |
| `summaries/project_forecast_context.json` | required analytical input | financial portion produced (`project_totals`) |
| `summaries/data_gap_register.json` | required analytical input | produced (`data_quality.gaps`) + source-unavailable gaps |
| `validation_report.json` (conclusion/checks) | required analytical input | produced (`conclusion`) |
| `mapping/owner_cost_code_family_crosswalk.jsonl` | required analytical input | **unavailable in Phase D** (`owner_crosswalk_unavailable`) |
| `mapping/ambiguous_mapping_candidates.jsonl` | required analytical input | **unavailable in Phase D** (owner family data not DB-native) |
| `summaries/mapping_coverage_summary.json` | required analytical input | partial / **unavailable** (owner/Procore coverage not DB-native) |
| `audit/reconciliation_report.json` | required analytical input | financial recon only; owner/Procore latest **unavailable** |
| `canonical/cost_entries.jsonl`, `canonical/monthly_actuals_*.jsonl` | derived intermediate | sourced in-memory from the snapshot |
| `canonical/owner_*`, `canonical/procore_*`, `mapping/*owner*`, `mapping/*procore*` | derived intermediate | **unavailable in Phase D** (file-only families, not DB-native) |
| `mapping/unmapped_owner_pay_app_rows.jsonl`, `mapping/unmapped_procore_pay_app_rows.jsonl` | evidence/debug artifact | not produced (not consumed by analysis) |
| `audit/source_validation_reports/*`, `audit/source_manifests/*`, `input_inventory.json` | evidence/debug artifact | not produced (package-file lineage) |
| `README.md`, `executive_forecast_summary.md`, schema reference | human-readable export | not produced (export is post-persistence, Phase E+) |
| `generate_forecast_context_package.py` self-copy, `manifest.json` (source SHA), package directory layout | obsolete package-coupling artifact | intentionally eliminated (in-memory object, no directory) |

## Consequences

- A typed, package-free context object exists for Phase E's calculation/persistence to consume.
- The DB-native runtime path takes no package dependency: no `SRC_FILES`, no package dir read/write,
  no manifest required, no TWN/Tropical/Synology constant, no silent package fallback.
- Redaction holds: `find_redaction_leaks(context.public()) == []`.
- Legacy file/DB-backed package generation is unchanged (its existing tests pass unmodified).

## Non-goals (deferred to Phase E)

- Normalizing owner/Procore/owner-crosswalk source families into DB-native rows + their analytical
  derivation (mapping coverage, reconciliation of owner/Procore latest, ambiguous candidates).
- Wiring the in-memory context into the analysis layer (`analysis/generate_forecast_analysis_package.py`
  still reads package files via `run_lineage`).
- Human-readable exports, full output persistence, UI changes, byte-parity with the legacy package.

## Remaining Phase E blockers

- Project the owner/Procore/crosswalk source families into the DB (extend Phase C) so the builder can
  populate the owner/Procore/crosswalk blocks instead of `available=false`.
- Refactor the analysis layer to consume the in-memory `DbNativeForecastContext` (or an adapter)
  instead of resolving context-package files via `run_lineage`.
- Wire the DB-native route (Phase B) to: snapshot → context builder → analysis → DB persistence.

## Guardrails

- No live-DB mutation; no external calls; no UI change; no full output persistence in Phase D.
- New module imports no `hb_assistant`; legacy builder untouched. No package directory, manifest, or
  `SRC_FILES` on the DB-native path.
