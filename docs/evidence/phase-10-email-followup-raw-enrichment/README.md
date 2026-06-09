# Evidence Manifest — Phase 10 Email Follow-Up Raw Enrichment (V45)

## Scope

Evidence for the Phase 10 email follow-up raw enrichment implementation: a review-safe V45
enrichment table fed by a bounded, sanitized, NON-persisted local raw email window and a local-only
model route, with explicit raw-local operator preview and pending daily-brief consumption.

## Safety Statement

This evidence directory contains **no** raw email body, raw excerpts, raw prompts, raw model
responses, body HTML, URLs, tokens, secrets, signed/download links, join links, or email-address
dumps. Proof artifacts carry counts, statuses, redaction flags, and SHA-256[:12] hash prefixes only.
The 13 Phase-10 guard column names (whose names assert the ABSENCE of raw prompt / response / body
content) are referenced by count, not spelled out verbatim, so the forbidden-string scan stays clean.

## Repo State

- Branch: `experiment/phase-10-email-followup-raw-enrichment`
- Base main HEAD: `d7c13a88e937163923eacc26329adebc6e4cec1f` (PR #11 merge)
- main touched: No · merge/rebase/push: No
- `config/config.yml`: present + untracked → left untouched (foreign/local)
- See `branch-state-proof.md`.

## Schema Proof

- Previous schema head: **V44** · New schema head: **V45**
- Migration: `src/hb_assistant/store/migrator.py` `V45_STATEMENTS` (`email_followup_enrichments` +
  5 indexes + 13 guard columns); `LATEST_SCHEMA_VERSION = 45`
- Fresh DB migration: pass (`tests/test_phase_10_email_followup_schema.py`)
- Copied (production) DB migration: V44 → V45 on a copy — see `schema-status-before.json`,
  `schema-status-after.json`, `v45-table-introspection.json`
- Guard-column proof: all 13 guard columns present and summing to 0 across V45 + relevant Phase-10
  tables — see `guard-column-proof.json`

## CLI Proof (on a copy of the production DB + a seeded copy)

- Dry-run (production copy): 0 eligible candidates, 0 persisted, exit 0 — `dry-run-cli-proof.json`
  (note: production has no accepted task/commitment candidates yet, so the production-copy run is a
  clean no-op; persistence/cap/idempotency are proven on a SEEDED copy below + at the engine layer)
- Apply with cap (seeded copy, cap=2, 3 eligible): persisted **2** — `apply-db-copy-proof.json`
- Idempotency rerun (seeded copy): row count stayed **2** — `idempotency-proof.json`
- Model-unavailable (seeded copy, no local models): persisted **0**, fail-closed —
  `model-unavailable-proof.json`
- Raw-local preview: synthetic-only proof of the opt-in gate + non-persistable marker —
  `raw-local-preview-synthetic-proof.md`

## Model / Routing Proof

- Task family: `email_followup_raw_enrichment`
- Default profile: `default_extract` (mistral-nemo:12b); local-only fallback chain
- Local-only route + no cloud fallback + fail-closed when no model — `local-routing-proof.json`
- Structured output validation (valid accepted, hallucinated citation rejected) —
  `structured-output-proof.json`

## Raw Boundary Proof

- Sanitizer redaction flags + leak-scan on synthetic input — `raw-window-sanitizer-proof.json`
  (HTML + attachments excluded; quotes/signatures/disclaimers stripped; URLs/join-links/tokens/
  secrets/emails/phones redacted; output passes the leak scan)

## Daily Brief Proof

- Pending rows labeled "Model-enriched / pending review"; low-confidence labeled "low confidence /
  needs review"; source-linked; no raw content — `daily-brief-pending-label-proof.json`

## Forbidden-String Scan

- `forbidden-string-scan-proof.md` — PASSED over this evidence directory; exceptions: none.

## Production DB Safety

- Production DB path resolved from runtime config (`PathPolicy.get_db_path`), not from memory.
- sha256 before == after (unchanged); all validation ran on `/tmp` copies —
  `production-db-unchanged-proof.md`

## Test Results

- Targeted (this feature, python3.12): `tests/test_phase_10_email_followup_*.py` +
  `tests/test_phase_10_raw_followup_window.py` — all pass.
- Schema/lifecycle regression (python3.12): `test_phase_10_schema`, `test_data_quality_table_inventory`,
  and the V26–V38 lifecycle-classification tests (bumped to 222) — pass.
- Changed source/test files clean under `ruff check` and `mypy` (per-file scope).
- Broad suite: pre-existing/environmental failures (Phase 09 retrieval/vector/semantic SDK gates,
  launcher/fastapi production-profile config pollution, data-quality / no-writeback proofs, repo
  sensitive-scan's two non-feature findings) are unrelated to this feature and reproduce on clean
  `main` (`d7c13a88`). See `test-results-summary.md`.

## Evidence Files

- `branch-state-proof.md`
- `schema-status-before.json`, `schema-status-after.json`, `v45-table-introspection.json`
- `guard-column-proof.json`
- `raw-window-sanitizer-proof.json`
- `raw-local-preview-synthetic-proof.md`
- `structured-output-proof.json`, `local-routing-proof.json`
- `dry-run-cli-proof.json`, `apply-db-copy-proof.json`, `idempotency-proof.json`
- `model-unavailable-proof.json`
- `daily-brief-pending-label-proof.json`
- `forbidden-string-scan-proof.md`
- `production-db-unchanged-proof.md`
- `test-results-summary.md`
