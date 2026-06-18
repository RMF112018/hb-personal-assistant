# ADR 263 — Forecast Phase 7: controlled final-package (analysis) DB parity

- **Status:** Accepted
- **Date:** 2026-06-18
- **Phase:** Forecast JSON/JSONL → SQLite transition, Phase 7
- **Builds on:** ADR 258 (Phase 2 lineage), ADR 259 (Phase 3 v59 source-domain read parity), ADR 260 (Phase 4 DB read adapter), ADR 261 (Phase 5 context-generator parameterization), ADR 262 (Phase 6 controlled context generation); v58 (PR #29), lifecycle contract (PR #30), Phases 2–6 (PRs #31–#35, Phase 6 merge `a1676b1e`).

## Context

Phase 6 proved file↔DB **context-package** parity and shipped a controlled, default-off runner
that can build a context package either file-backed or DB-backed in a temp root. The next question
is downstream: **given DB-backed context parity, does the next forecast-generation layer produce a
parity-equivalent final output when fed a DB-backed context package instead of a file-backed one?**

Phase 7 answers that for the **immediate** downstream layer. It is still a controlled temp-root
parity phase — **not** a production DB cutover, and it changes no production defaults.

## Decision

### Downstream layer selected by repo truth: the analysis package

The repo's forecast generation is a chain, not one node. By repo truth (and confirmed with the
operator), Phase 7 uses **`analysis/generate_forecast_analysis_package.py`** (`run-analysis`):

- It is the **immediate** layer that consumes the context package and **only** the context package
  (its sole `resolve_upstream("context", ...)` call); no analysis_v2/schedule/intelligence inputs.
- It is **deterministic** by repo truth — stdlib only, `Decimal` money math, sorted output, no RNG,
  **no LLM/Ollama/network**. So no deterministic/mock mode needs to be introduced (and none was).
- It is therefore the only downstream generator that is **self-contained and CI-synthesizable** from
  the Phase 6 synthetic context.

`forecast_intelligence` (needs context + analysis_v2) and `forecast_comprehensive` (needs the entire
upstream chain) were explicitly excluded — they would convert Phase 7 into a broad synthetic-pipeline
reconstruction. Their model-backed/full-chain parity is deferred.

### A narrow subprocess-wrapping runner

`analysis/final_forecast_runner.run_final_forecast_generation(*, context_package, project_key="tropical", run_id=None, deterministic=True) -> dict`. The analysis generator is a self-contained script (`__main__`-only, not an importable API), so the runner wraps its subprocess execution rather than refactoring it. It is CFR-only (stdlib + `common.run_lineage`); it has **no `hb_assistant` dependency** — the DB-ness is already baked into the context package by the Phase 6 runner, and the analysis generator only reads files.

### Controlled context-package input — hard pin, no latest-glob

The repo-sanctioned way to point a downstream stage at one specific context package is reused, not replaced:

- The runner mints a **temp** run-lineage state (`run_lineage.start_run_state`, with the state file and its `current_<project>` pointer written under the temp data root — never the repo's `.cfr_run_state/`) so the generator's `active_data_root` resolves to the temp data root instead of the live Synology default.
- It sets `CFR_CONTEXT_STAMP` to the context package's stamp. The generator's `resolve_upstream` treats this as an **explicit override (precedence 1)** and **fails closed** if that exact package is absent — it never falls back to latest-glob, the live root, or stale config names. This is a *hard pin*, proven by a test that places a decoy context package in the data root and confirms a different (absent) requested stamp is refused rather than discovered.
- The subprocess receives an explicit env copy; the runner never mutates global `os.environ` (nothing to restore). Production `run-analysis`, latest-glob, config-pin, and run-state behavior are untouched — the controlled path only adds a temp state + override inside the runner.

### Fail closed before subprocess execution

The runner raises `FinalForecastRunnerError` (before the subprocess starts) when: `context_package` is missing/not a dir; its name isn't a tropical context package; it is structurally invalid (missing `manifest.json` / `validation_report.json` / `canonical/` / `summaries/`); `project_key != "tropical"`; `deterministic` is False (no model-backed mode exists); the context data root is at/under the live Synology root; or an analysis package already exists in the data root (so the produced output is unambiguous). The generator's own fail-closed resolver error (missing pinned context) surfaces as a nonzero subprocess exit, mapped to the same error.

### CLI command (additive, non-breaking)

`final-forecast-generate --project tropical --context-package <path> [--run-id <id>]` calls the runner in-process, prints structured JSON metadata on stdout (generator chatter redirected to stderr, mirroring Phase 6), and returns rc 3 on refusal. No `--out-dir`/`--stamp`: the analysis generator owns its output location (its data root) and stamp (`datetime.now()` at import, not freezable); the operator controls the output location implicitly by choosing where the context package lives. No deterministic flag (analysis has no other mode). Existing commands are unchanged.

### Final-output comparison + volatile normalization

The parity test runs the Phase 6 runner twice (file-backed and DB-backed context, each under its own temp data root sharing one context stamp), runs the analysis runner against each, and compares the two analysis packages structurally. **Normalized only:** the temp data-root path (which contains both the consumed-context path and the analysis output path), the analysis package directory name, and the approved volatile keys `generated_stamp` / `generated_timestamp_local` / `package_name` / `input_root` (+ `sha256` / `size_bytes`). **Never normalized:** budget-code keys, actuals, forecast/recommendation values, financial values, validation statuses/conclusions, row counts, domain values, or source row content. With identical context content, the analysis packages are equivalent after normalization.

## Live safety

No Phase 7 test writes under the live Synology root or touches the live DB; all generated context and analysis packages are asserted under `tmp_path`. The optional live-source smoke remains a Phase 5/6 concern, skipped/local only. The runner refuses a live-root data root outright.

## Scope / deferrals (unchanged in Phase 7)

- Production DB-backed default enablement (DB-backed stays opt-in).
- Latest-glob / config-pin / run-state replacement (reused, not replaced; the temp state is controlled-path only).
- Full DB-domain migration; owner/Procore/control/staffing/schedule/model-control DB reads.
- Model-backed / `forecast_intelligence` / `forecast_comprehensive` / final integrated-forecast parity.
- The −$3.42M reconciliation gap.
- Class-based generator cleanup.

## Consequences

- **No schema change** (`LATEST_SCHEMA_VERSION` stays 59; no v60). **No lifecycle-contract change** (`table_count` stays 387). **No `hb_assistant` source change** (the runner is CFR-only; the analysis generator is untouched).
- There is now a safe, explicit, default-off way to prove that the immediate downstream layer produces a parity-equivalent analysis package from a DB-backed context package vs a file-backed one, in a controlled temp-root workflow.
- Changed surface is additive: one new CFR runner module, one new CFR CLI subcommand, one new test module, and this ADR.
- Live DB untouched (still v58, no v59 domain tables); no live-root output written.
