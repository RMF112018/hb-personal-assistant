# 185 — Unified Source-Refresh Orchestrator

**Objective:** give the operator one safe command that performs the full daily local
data refresh required before Daily Brief V2 generation — Procore + Microsoft Graph
sync into local SQLite, then the Phase-09 second-brain intelligence rebuild — instead
of running auth, per-source sync, retrieval rebuild, vector rebuild, and daily-brief
packet commands by hand and in order.

## Command

`hb-assistant construction-agent refresh-sources [--all] [--apply] [--confirm]
[--procore-only] [--graph-only] [--skip-vector] [--skip-daily-brief-proof]
[--date YYYY-MM-DD] [--json]`

- **Dry-run is the default** (`--apply` off): plan only, no DB writes.
- `--apply` upserts to local SQLite only and **requires `--confirm`** (fail-closed).
- Any **live external read** (Procore live GET, Graph calendar/files) additionally
  requires `--confirm` and the relevant live gate (`HB_PROCORE_LIVE=1` for Procore, a
  delegated token for Graph); without it those reads are skipped, never silently run.

The CLI is a thin adapter in `cli/construction.py`; all logic lives in
`hb_assistant.source_refresh.SourceRefreshOrchestrator`.

## Design

The orchestrator models the stage-isolation idiom of
`automation/orchestrator.py::MorningRunOrchestrator`: each stage runs through a
single `_stage(name, fn)` guard that records a structured failure and degrades the
overall status without aborting the run. It composes existing surfaces in-process
(imports + calls) — it never shells out to other CLI commands.

Stages, in order:

1. **preflight** — schema/DB readiness (`SQLiteMigrator.current_version()` vs
   `LATEST_SCHEMA_VERSION`), repo SHA, local DB path, no-writeback attestation. Under
   `--apply --confirm` it auto-migrates a behind-schema DB to latest; dry-run never
   migrates.
2. **procore** — `check_auth_status()`; fails closed for live reads when not ready.
   Iterates mapped **pilot** projects (`load_procore_projects()`), calling
   `procore.sync.run_sync(project_key=…)` per project (the coordinator rejects a
   multi-project sentinel). Live apply runs only with `--confirm`,
   `live_env_active()`, and `assert_live_mapping_strict`; otherwise it produces a
   dry-run plan. Counts are collected per project.
3. **graph** — `DelegatedAuthProvider.status_info()`. `mail_thread_summary` is
   local-only and always runs (`dry_run = not apply`). `calendar_event_index` and
   `files` read from Graph even to plan, so they require `--confirm` (and a token);
   without it they are skipped (`confirm_required_for_live_read`), and when a live
   read is intended without a token they are `blocked_auth_not_ready`.
4. **rebuild** — `build_approved_source_manifest`, `build_coverage_parity_closeout`,
   `build_vector_index_dry_run` (+ `build_vector_index_apply` under apply, tolerating
   `apply_blocked` when retrieval extras are absent), `build_no_raw_vector_index_proof`,
   `build_daily_brief_packet_v2` (+ V2 packet/quality proofs), and the MCP no-raw /
   no-writeback attestations. **Sub-proofs run with `write_evidence=False`** — their
   default `evidence_dir` targets the authoritative per-phase bundles, and the refresh
   command must not rewrite another phase's evidence.
5. **finalize** — one consolidated JSON object: `command`, `status`
   (`ok`/`degraded`/`failed`), `dry_run`/`apply`, per-source auth + sync summaries,
   `sqlite_upsert_summary` (`{inserted,updated,skipped,failed,planned}` by source and
   total), retrieval/vector/daily-brief summaries, `guardrails`, `warnings`,
   `failures`, and a derived `next_operator_action`.

## Guardrails

All inherited from the underlying surfaces and re-attested in the output: no Procore
writeback; no Microsoft 365/Graph writeback; no raw email/calendar body or join URL;
no raw Procore payload (metadata/read-models only); no prompts/model responses
persisted; no vectors/vector text in SQLite; MCP exposure unchanged; fail closed when
auth is not ready; fail closed when `--apply` lacks `--confirm`. Partial source
failure yields `degraded` with failures surfaced, never hidden. State is local SQLite
only; serialized evidence passes a defense-in-depth redaction scrub.

## Evidence

`docs/evidence/source-refresh/` holds the dry-run pair (real), the local-apply proof
pair (external reads gated, operator-pending for a true live run), and the closeout
roll-up. The refresh command writes only its own bundle.

## Tests / validation scope

`tests/test_sources_refresh.py` (CliRunner + isolated config) covers gating,
fail-closed auth, partial-failure degradation, upsert-count reporting, skip flags,
V2 packet generation, auto-migrate, and no-raw output. `hb_assistant.source_refresh.*`
is opted into strict ruff + mypy scope in `pyproject.toml`.
