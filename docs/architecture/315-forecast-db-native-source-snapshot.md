# 315 — Forecast generation: DB-native source-domain snapshot (read model)

- Status: accepted
- Date: 2026-06-25
- Phase: Forecast Run Center remediation — Phase C (DB-native source-domain read model)
- Related: ADR 314 (DB-native contract & routing boundary), ADR 313 (DB-native boundary, fail-closed),
  ADR 303 (P3 DB-native model-input accessors)

## Context

ADR 314 listed Phase C as *package-free DB-source context*. Forecast inputs today come from JSONL
**source packages** (or, behind the P3 opt-in, the same three v59 tables via CFR's `db_source_adapter`).
Phase C builds the deterministic, typed, path-free **source snapshot read from the local DB only** —
the input object the later DB-native engine (Phase D) will consume — without touching CFR calculation
or the UI, and without depending on any source/context/analysis package.

## Decision

Add `construction/analytics/forecast_db_native_source_snapshot.py`:
`build_db_native_source_snapshot(project_key, *, db_path=None, source_package=None) ->
DbNativeSourceSnapshot` (frozen dataclasses; `.public()` is the serializable, redaction-safe contract).

1. **Reuse, don't re-derive.** Identity + readiness + maturity come verbatim from
   `ForecastGenerationProjectReadModelService.list_generation_projects()` (authoritative); the forecast
   window + schedule summary from `ForecastGenerationDateDefaultsService.resolve()`; the three v59
   financial families from `source_domain_repository.read_*_from_db` (clean `json.loads(raw_json)`
   business rows, deterministic business-key order). The snapshot only **splits** the read model's
   coded `readiness_reasons` into `blockers` (∩ {`no_project_identity`, `no_financial_basis`} when
   status is `blocked`) and `warnings`. `sparse` derives from the read model's maturity
   (`baseline_only`/`cost_informed`), not from ad-hoc amount math.

2. **Required basis vs optional enrichment.** Typed rows are carried only for the three v59 financial
   families (the engine's required basis). Optional `procore_ep_*` enrichment families — commitments
   (`procore_ep_commitment_contracts`), commitment changes (`procore_ep_commitment_change_orders`),
   change events (`procore_ep_change_events`) — are reported by **availability + count only** (no
   normalized rows) via narrow per-family `COUNT(*) … WHERE project_key=? AND is_current=1` queries,
   `_table_exists`-guarded. A missing/empty family yields `present=false, row_count=0` and a coded
   `enrichment_family_unavailable:<name>` warning — it never fails the snapshot. Full enrichment-row
   normalization is deferred to the engine/modeling phases.

3. **Missing vs zero is explicit.** A `SourceFamily` with `present=false` means *no rows exist*; a
   `present=true` family whose rows carry `0` amounts means the data exists and the zeros are real
   input facts. `sparse` (thin-but-present) is distinct from `blocked` (no identity / no basis).

4. **`source_package` is internal only.** It is used solely to select the active v59 batch and is kept
   as a non-public dataclass field; `public()` never emits it. Public provenance is package/path-free:
   `financial_basis.active_source_batch_present` + `active_source_batch_row_counts`,
   `provenance.row_counts_by_family`, `provenance.source_families_present`. Route-facing contracts stay
   package/path-free.

5. **Read-only + CFR-independent.** The builder resolves the DB path and opens it `mode=ro`; it
   mutates nothing. The module imports no CFR / `package_resolution` / context / analysis / package
   workflow symbol (guarded by an AST boundary test) and never falls back to source packages.

## Consequences

- A stable, serializable source contract exists for Phase D to consume, decoupled from package files.
- Redaction is preserved end-to-end; `find_redaction_leaks(public()) == []` and no `source_package` /
  `cost_forecast_json_package` / `source_path` / `raw_json` / local path appears in public output.
- Readiness semantics remain single-sourced in the read model (no drift).

## Non-goals (deferred)

- Forecast calculation / engine, DB persistence of outputs, UI wiring — unchanged in Phase C.
- Normalized enrichment rows (commitment/change-event line items) and amount/exposure math.
- Persisting `source_snapshot_id` provenance (the Phase B contract field) — still deferred.

## Remaining Phase D blockers

- A DB-native calculation engine that consumes `DbNativeSourceSnapshot` (no file `source_package` /
  `analysis_package`) and produces forecast outputs.
- Normalized enrichment-family inputs (commitments / change events) when the engine needs them.
- Direct DB persistence of engine outputs + certification proving no package dependency remains.

## Guardrails

- No live-DB mutation; reads are `mode=ro`. No external calls. No CFR calculation change. No UI change.
- No source/context/analysis package dependency; no silent package fallback. No hard-coded
  TWN/Tropical filesystem constants; multiple project keys supported.
