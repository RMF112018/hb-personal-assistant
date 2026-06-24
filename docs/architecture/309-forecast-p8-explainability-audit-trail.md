# 309 — Forecast P8: explainability / audit trail (Gap 9)

- Status: accepted
- Date: 2026-06-24
- Phase: forecast-model remediation P8
- Gap: #9 (explainability / audit trail incomplete)

## Context

The run-output projector (`construction/forecast/output_projection_engine.py`) writes the v63
`forecast_output_*` family, but `forecast_output_narratives` (V63) shipped with **zero writers** — a
forecast run produced no reason trail. There was also no model-version reference on the output, no
human-override audit view, source-data QA was a binary "rows present / no rows", and the provenance
digests that already exist (`forecast_outputs.source_sha256`, the V72
`forecast_run_model_versions.methodology_sha256` + `accuracy_package_stamp`) were never chained
across context → analysis → output.

`forecast_output_narratives` and all the QA columns already exist in the live schema, so **P8 is
derivation + wiring only — no migration**. The projector writes only to a NON-LIVE temp DB
(`is_live_db_path` guard); turning the audit trail on adds rows to a previously-empty table, so it
ships **default-off** behind a flag to keep flag-off output byte-identical.

### Repo-truth correction (vs the planning note)

The plan and its gate review assumed `completeness` / `mapping_quality` / `score` on
`forecast_data_availability_profiles` were still reserved `None`, requiring a P8 edit to
`decision_support_engine.py`. **Merged P5 (ADR 308) already populates all of these.** There were no
reserved columns left to fill, and changing that engine's `raw_json` would only risk P5's
byte-identity tests. Per CLAUDE.md (repo truth > planning note), **P8 leaves
`decision_support_engine.py` untouched**; the "source-data QA rationale" deliverable is satisfied by
the output-side `source_qa` narrative instead.

## Decision

1. **Default-off flag.** `HB_FORECAST_EXPLAINABILITY_ENABLED` (const + `DEFAULT_CONFIG` entry +
   `resolve_explainability_enabled`, precedence explicit > env > settings > default-False), mirroring
   P6's `model_governance_enabled`. Resolved once in `project_run_output` and threaded as an explicit
   `explainability_enabled` param into the pure planner (mirrors how P2b threads `operator_assumptions`).
   Flag-off ⇒ no narrative rows, `source_sha256` stays `None`, output byte-identical.

2. **Narratives populate the existing table — no new schema.** A new pure, deterministic
   `output_narrative_builder.py` (no LLM, no CFR import) emits five `scope`s into
   `forecast_output_narratives`:
   - `project` — header EAC/FAC/CTC/variance + code/risk/override/warning counts.
   - `budget_code` — per-recommendation numbers, action, confidence, risk count, overridden flag.
   - `human_override` — one row per operator dollar override, **derived** from the
     `operator_value_override` change rows already in `planned["changes"]` (no separate history
     table — see "Override history" below).
   - `source_qa` — null / zero projected-cost counts, duplicate budget-code keys, and the
     `forecast_period` staleness signal over the analysis-package recommendations.
   - `lineage` — the context→analysis→output package-sha256 chain.
   `output_repository.py` gains `upsert_output_narrative` (idempotent on the table
   `UNIQUE(output_id, scope, narrative_key)`) + `read_output_narratives_from_db`, registered in
   `_WRITERS` and the `_prove_parity` readers so narratives get DB↔package parity coverage.

3. **Override history = derivation, not a new table.** The verbatim spec says "a human-override
   history table". The override record already exists, fully typed, as
   `change_type='operator_value_override'` rows in `forecast_output_changes`. P8 surfaces the audit
   *view* as `scope='human_override'` narratives rather than duplicating that data into a new V73
   table — a migration whose only driver would be this one phrase. **Accepted:** the dedicated
   typed/indexed table is deferred; if a query surface later needs it, it is an additive follow-on.

4. **Package-sha256 chain.** The `lineage` narrative assembles: `context_sha256` (over the context
   package's `canonical/budget_codes.jsonl`, when supplied), `analysis_sha256` (now also written to
   the long-empty `forecast_outputs.source_sha256` column, over the analysis package's manifest +
   recommendations + risk-register files), `output_sha256` (a **content** hash of the projected
   detail rows, excluding the narratives themselves and the volatile path/timestamp keys, so it is
   stable across runs of identical inputs), and — when a V72 provenance row exists for the run —
   `methodology_sha256` + `accuracy_package_stamp`, plus the `prior_run_id` from the
   `current_vs_prior` change row. The `lineage` row is built in the apply transaction after
   `apply_plan` (it needs the DB) and folded into the plan + parity. Every upstream sha degrades to
   `None` when its package/provenance is absent (degraded-not-fatal).

## Consequences

- One PR, **no schema/migration/table_count change**, no `hb_assistant` schema touch, no external
  systems, no live-DB write — so no sensitive-operation gate.
- New tests: `test_forecast_output_narratives_p8.py` (presence, flag-off byte-identity, override
  audit, apply+parity, idempotent re-apply), `test_forecast_lineage_completeness_p8.py`
  (`source_sha256` set, chain present, methodology folded in, determinism), `test_forecast_source_qa_p8.py`
  (null/zero/dup + staleness). All added to `scripts/test-forecasting.sh`.
- Deferred: the dedicated human-override-history table (V73); a numeric confidence score (deferred
  in P5); any live-DB write.
