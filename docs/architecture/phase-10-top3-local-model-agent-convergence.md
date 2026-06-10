# Phase 10 — Top 3 Local-Model Agent Convergence

Status: implemented on `experiment/phase-10-top3-local-model-agent-convergence` (base `ebd8e74a`).
Scope: converge three previously-separate local-model capabilities into one coherent, default-on,
source-linked operator experience. Local-first; no schema migration; no external writeback.

## Three converged candidates

1. **Daily Brief Intelligence / Synthesis Convergence** — one operator-facing section labeled exactly
   **Model Enriched Intelligence**, default-on across browser, Obsidian, status JSON, and CLI JSON.
2. **Scheduler / Daily-Run Live Hardening** — the scheduled run produces the same final surfaces and
   exposes legible install/status diagnostics (effective posture, readiness, last-run).
3. **Email Follow-Up Raw Enrichment Productionization** — V45 raw enrichment becomes a bounded, capped,
   idempotent daily-run apply stage plus a read-only readiness surface; pending rows feed the section.

## Model Enriched Intelligence contract

`construction/second_brain/local_ai/model_enriched_intelligence.py`:
- `build_model_enriched_intelligence(...)` composes the **intelligence-adapter** result
  (`build_daily_brief_intelligence`, source-linked advisory bullets) with the **V45 pending follow-up**
  section (`build_pending_email_enrichment_section`). Returns a raw-safe object with `enabled,
  available, label="Model Enriched Intelligence", degraded, withheld_reason, candidate_count,
  source_link_count/coverage, bullets_seen/kept/dropped, unknown_source_ids_count,
  pending_followup_count, route_selected_profile, route_model_name, terminal/generation_profile_id,
  fallback_chain, warnings, guardrails, intelligence, pending_followup`.
- `status_block(mei)` → compact raw-safe status (no bullet bodies).
- `render_model_enriched_markdown(mei)` and the browser card (`daily_run_html._render_model_enriched_card`)
  render the exact `## / <h2> Model Enriched Intelligence` heading; the pending V45 rows are folded in
  as a subsection under that one label.

### Two-call design (intentional)
Convergence is at the **render/status contract layer**, not by merging upstream model calls. The
narrative synthesis (`synthesize_daily_brief`) remains the brief body; the adapter produces the
advisory bullets. This reuses two tested paths at lowest regression risk; a single unified model call
is explicitly out of scope (see evidence `04`, `24`).

### Source-link + fail-closed
Every advisory bullet must cite ≥1 known candidate id (alias-mapped); unknown ids are counted and
dropped; zero survivors → the body is withheld and the deterministic brief is preserved. Model
unavailable / JSON-invalid / schema-invalid / redaction-failing → withheld + `degraded`; pending
(deterministic) rows still surface. MEI degradation is advisory and does **not** fail the run.

## Default-on behavior

- `second-brain daily-run run`: `--model-enriched-intelligence/--no-model-enriched-intelligence`
  (default ON) and `--email-raw-enrichment/--no-email-raw-enrichment` (default ON; apply-only),
  `--email-raw-enrichment-max-persist N`. Back-compat aliases `--with-intelligence` (JSON twin) and
  `--with-email-raw-enrichment` retained (the latter's negative token renamed to
  `--no-with-email-raw-enrichment` to avoid a flag collision). `--open-browser` stays reserved/no-op.
- The `run_daily_local_agent` **function** defaults these OFF (mirroring `synthesize_brief`) so direct
  callers/tests opt in explicitly; the CLI and installed scheduler set them ON — that is the operator
  default-on behavior.

## Local-only model routing

Both paths route through `model_router.route_task_family` (fail-closed, no cloud route exists):
`daily_brief_synthesis_quality` (adapter) and `email_followup_raw_enrichment` (V45). Availability is
probed read-only via `build_local_model_status` (Ollama); unavailable → withheld/skip, never a
substitution or cloud fallback.

## Scheduler posture

`daily_run_scheduler.DailyRunLaunchdManager` gains `model_enriched_intelligence` /
`email_raw_enrichment` knobs emitted into `ProgramArguments` (default-on, with `--no-open-browser`).
`preview_install()` / `status()` now surface `effective_config` (MEI, email-raw, browser generation,
**browser_auto_open=false**, DB/vault/path redactions), expanded `readiness` (executable/workdir/log
readiness + redacted paths, plist_exists, `blocking_diagnostics`), weekday intervals, catch-up-on-wake
explanation, and `last_run` (latest status path, last result, last successful brief). Tests never run
`launchctl`.

## V45 raw enrichment productionization

- **Readiness** (`email_followup_readiness.build_email_followup_enrichment_readiness`): read-only funnel
  over accepted tasks/commitments with per-reason skip counts (`no_candidate_id`,
  `no_candidate_source_refs`, `no_email_source_ref`, `no_raw_email_content`, `already_pending`,
  `already_final_review_status`, `local_model_unavailable`, `raw_policy_disabled`, `source_link_invalid`,
  `unsupported_candidate_type`), a `local_model_available` gate, route metadata, and a bounded sample of
  safe candidate ids. Raw existence is determined **only** from source refs / hashes / window-builder
  `available` metadata — raw body text is never loaded or printed. CLI: `follow-up-watch enrich-readiness`.
- **Apply stage** (`daily_run._run_email_raw_enrichment_stage`): runs only in apply mode when enabled +
  eligible + route available + cap>0. Dry-run reports `would_persist` and writes nothing; apply persists
  review-safe rows capped by `max_persist`, idempotent, source-linked, with the engine's per-field raw-leak
  guard. Receipt: `{stage, status: ok|skipped|degraded|failed, eligible, would_persist, persisted,
  skipped_by_reason, degraded_reason}` (raw-free). Ordered before the MEI build so newly-persisted pending
  rows are consumed the same run.

## DB-copy proof & safety boundaries

- Production DB resolved via `PathPolicy.get_db_path()`; copied to `/tmp`; sha256 unchanged before/after
  (evidence `20`). Seeded-copy fixtures (clearly labeled) prove dry-run/cap/idempotency/integration.
- V45 guard columns (`raw_*_persisted=0`, `*_writeback_performed=0` CHECK) stay zero (`19`).
- No raw bodies/prompts/responses/full-URLs/tokens/signed links in any repo artifact, status, log, or
  evidence (egress scrub + `scan_daily_run_html` + forbidden-string scan `17`). No schema migration.

## Non-goals

Schema migration; single unified model call; cloud routing; any external/Graph/Procore/calendar/email
writeback; raw-content persistence; browser auto-open; new frontend.

## Residual limitations

See `docs/evidence/phase-10-top3-local-model-agent-convergence/24-known-limitations.md`.
