# P8 — Explainability / audit trail (Gap 9)

- Phase: forecast-model remediation **P8**
- ADR: `docs/architecture/309-forecast-p8-explainability-audit-trail.md`
- Scope: derivation + wiring only — **no migration, no schema/table_count change, no hb_assistant
  schema touch, no external systems, no live-DB write**.

## What landed

1. **Flag** `HB_FORECAST_EXPLAINABILITY_ENABLED` (default off) in
   `construction/analytics/forecast_runtime_config.py` — const + `DEFAULT_CONFIG` entry +
   `resolve_explainability_enabled` (explicit > env > settings > default-False). Mirrors P6.

2. **`output_narrative_builder.py`** (new, pure, deterministic, no LLM / no CFR import) — emits five
   narrative `scope`s into the previously-empty `forecast_output_narratives` (V63): `project`,
   `budget_code`, `human_override`, `source_qa`, `lineage`.

3. **`output_repository.py`** — `upsert_output_narrative` (idempotent on
   `UNIQUE(output_id, scope, narrative_key)`) + `read_output_narratives_from_db`, registered in
   `_WRITERS` and the `_prove_parity` readers.

4. **`output_projection_engine.py`** — threads `explainability_enabled` from `project_run_output`
   into the planner; builds the four pure narratives at the end of the plan phase; sets the
   long-empty `forecast_outputs.source_sha256` (analysis sha); builds the `lineage` narrative in the
   apply transaction (context/analysis/output sha chain + V72 methodology sha + `prior_run_id` when
   present); added `forecast_output_narratives` to `GUARDRAILS["tables"]` and `narratives` to
   `_PLAN_KEYS`.

## Key decisions

- **Human-override "history table" → derivation.** Surfaced as `scope='human_override'` narratives
  derived from the existing `operator_value_override` rows in `forecast_output_changes`; the
  dedicated V73 table is deferred (its only driver was the spec's one-word "table").
- **No `decision_support_engine.py` change (repo-truth correction).** Merged P5 (ADR 308) already
  populates the availability QA columns; the source-QA deliverable is met by the output-side
  `source_qa` narrative (null/zero/dup + staleness). See ADR 309.
- **`output_sha256` is a content hash** (excludes the narratives + volatile path/timestamp keys), so
  the lineage chain is deterministic across runs of identical inputs.

## Validation

See `validation.txt` / `new_tests.txt`. Forecasting bundle 895 passed / 0 failed (P5 baseline 883 +
12 new P8); schedule bundle 113 passed / 0 failed (schema canary — confirms no schema drift). Flag
off ⇒ zero narrative rows and `source_sha256` null (byte-identical), asserted directly.
