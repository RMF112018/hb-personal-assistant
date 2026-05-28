# Architecture Documentation

This directory contains living architecture and decision records for the HB Personal Assistant project.

- `01-scaffold-overview.md` — Phase 1 foundation (PathPolicy, Typer CLI, config loader)
- `02-…` through `12-launchd-automation-and-diagnostics.md` — Phase evolution (store, classification, files, retrieval, automation/orchestrator, diagnostics)
- `13-testing-hardening-and-final-closeout.md` — Phase 13 closeout record (`v1.3.0`), preserved as historical evidence
- `remediation-gap-closure.md` — Prompt 01 repo truth reconciliation and remediation acceptance baseline
- `remediation-validation-baseline.md` — Prompt 04 validation baseline and scoped standards (pytest/ruff/mypy reconciliation)
- `remediation-delegated-graph-proof.md` — Prompt 05 runtime delegated Graph proof refresh and truthful gap reporting
- `remediation-bounded-graph-paging.md` — Prompt 07 bounded, deterministic Graph paging across mail/calendar/drive clients
- `remediation-provenance-safe-file-ingestion.md` — Prompt 08 provenance-safe ingest contract (`files sample` vs real `files ingest`)
- `remediation-integrated-daily-brief-content.md` — Prompt 09 Daily Brief sections wired to current context/store sources with explicit empty states
- `remediation-bounded-content-sensitive-scan.md` — Prompt 10 bounded line-level sensitive scanner with redacted findings output
- `remediation-final-truthful-closeout.md` — Prompt 11 final remediation closeout status and acceptance gate evidence
- `remediation-hardened-app-support-permissions.md` — Addendum Prompt 02 path initialization hardening and `diagnostics paths` repair guidance
- `remediation-db-readiness-and-structured-dry-run-blocking.md` — Addendum Prompt 03 DB readiness gate and dry-run JSON blocked status behavior
- `remediation-bounded-body-mention-detection.md` (P05) — Addendum Prompt 05 bounded body inspector + MailClient fetch + classifier fallback (beyond preview)
- Prompt 06 final closeout: `docs/evidence/remediation-addendum/final-closeout/` + truthful **CONDITIONALLY_ACCEPTED_WITH_EXTERNAL_ADMIN_CONSENT_BLOCKER** (DNS language corrected as misattribution in Phase 14 Prompt 01; see `docs/evidence/phase-14-local-runtime-workstream-intelligence/prompt-01/`).
- `remediation-blocker-taxonomy-correction.md` — Phase 14 Prompt 01: blocker taxonomy correction, removal of stale DNS claims, D-P14-011 decision record, and prompt-01 evidence package.
- `remediation-idempotent-action-persistence.md` — Phase 14 Prompt 03: idempotent action upsert by stable_key (completed status preserved), action-aware source link helper in Registry, service refactor, and duplicate/completed/migration tests.
- `remediation-signal-integration-action-intelligence.md` — Phase 14 Prompt 04: multi-source bounded signal loading (body mentions, parser, calendar, file review, retrieval) into actions extractor, phrase mapping for full actionTypes, confidence + weak monitor, with seeded-DB tests and CLI dry-run validation.
- `remediation-morning-run-orchestration-upgrade.md` — Phase 14 Prompt 07: full 05 stage model in orchestrator with Graph consent blocker classification (skipped_* for Graph while local stages continue), P02-P06 integration (actions, context, brief+obsidian provenance), explicit failure isolation, and exact 05 JSON contract (blocker_classification + stages array).
- `docs/decisions/` — Closed technical decisions (D-CLI-001 etc.)

- Prompt 02: Dry-Run Semantics and Run Ledger Policy — explicit documentation of allowed ledger/evidence writes vs forbidden business object mutations (action_items, source_links, Obsidian notes); CLI notes aligned; tests proving zero mutations in dry-run (before/after row counts); evidence at `docs/evidence/mvp-local-runtime/02-dry-run-policy-proof.md`.
Remediation context: implementation reached `v1.3.0`, but acceptance is gated on remediation validation; prior closeout claims are superseded pending green remediation evidence.

For the full phased plan and research, see `docs/plans/my-pa-phase-0/`.

**P07 addition**: Public operator-facing documentation for the local MVP (no code reading required) lives at `docs/operations/mvp-local-runtime-operator-guide.md` + supporting evidence at `docs/evidence/mvp-local-runtime/07-operator-runbook-and-limitations.md` and `06-known-limitations.md`. Covers venv, diagnostics, morning dry-run, launchd management, what gets written vs never, Graph deferred / Prompt 9 readiness, and all operational paths.

**Phase 03 Prompt 01A (Endpoint Reference & Contract Enrichment):** See `docs/evidence/construction-intelligence-phase-03/01A-procore-endpoint-reference-verification.md` + matrix JSON + search result. Modern REST v1.x paths reconciled for core operational/financial endpoints against official developers.procore.com/reference/rest; unverified candidate catalog materialized from the Phase 03 package; new test file + guardrail tests added; all hard GET-only/excluded/deferred/sensitive-review rules preserved. Minimal pointer only (surgical).

**Phase 03 Construction Intelligence / Procore note (Prompt 00 rebaseline):** See `docs/evidence/construction-intelligence-phase-03/00-repo-truth-and-phase-02-rebaseline.md` (repo truth audit, Phase 01/02 acceptance posture, current 4-module procore/ contract layer + seeds vs Desktop/procore_hbintel_data_model_package/ research as effective Phase 03 input — layered canonical model, priority financial/operational entities, SharePoint recs, 13-Assumptions gaps). No prior coverage of construction/procore/phase-03 surfaces in 00-13 or remediation- docs. Minimal pointer only (surgical).

**Phase 03 Prompt 01 (API Research & Decision Register):** See `docs/evidence/construction-intelligence-phase-03/01-procore-api-research-summary.md`. High-level official Procore docs research (OAuth, base URLs/environments, REST paths/versioning, pagination/filtering/sorting, rate limits/quotas, errors, changelog/best practices) with full Decision Register (URL | Access Date | Fact | Decision/Rationale | Confidence | Notes/Risks). 4 parallel explore sub-agents spawned for the research areas (active with web_search/web_fetch on developers.procore.com, 0 errors). All guardrails preserved (research-only, no code/seed/test changes, no Procore calls, evidence stays evidence-only). Sources from official pages (oauth-*, development-environments, pagination, filtering-on-list-actions, rate-limiting, error-reference, reference/rest). Minimal pointer only (surgical).

**Prompt 02 (2026-05-27):** App profile + environments schemas/seeds + full secret storage/loader in src/hb_assistant/procore/config.py (Keychain/env/0600 file, no-leak, OOB enforced). See evidence/construction-intelligence-phase-03/02-procore-app-credential-posture.md and 01-*-augmented.md. (minimal pointer per plan)

**Prompt 04 (2026-05-27):** GET-only Procore HTTP client foundation (http_client.py + redaction.py + errors.py + pagination.py) with injectable transport, runtime secret via Prompt_02 config.py only, correlation IDs, aggressive redaction, Link+cursor pagination + rate-aware retry, safe normalized errors, and static AST GET-only scanner. See evidence/construction-intelligence-phase-03/04-procore-client-foundation-proof.md.

**Prompt 05 (2026-05-27):** Endpoint contract model + config strengthened (explicit categories foundation/project_controls/financials; hard GET-only; financials force review_required + sensitive; verified paths only from Prompt_01A/01; deferred/excluded explicit; fail-closed tests). See evidence/construction-intelligence-phase-03/05-procore-endpoint-contract-proof.md.

**Prompt 06 (2026-05-27):** Pilot project mapping + company 5280 validation (new dedicated procore_project_mapping.seed.yaml with explicit pending for hilltop*; CLI list/status coverage for mapping/projects/companies + enhanced validate surfacing company context; HB# vs Procore ID separation tests; 3 explore sub-agents + safe discovery only). See evidence/construction-intelligence-phase-03/08-procore-pilot-project-mapping-proof.md. (minimal pointer, surgical).

**Prompt 07 (2026-05-27):** Endpoint audit dry-run construction + optional explicit manual live proof (extends auditor.py + models with new verdicts/receipts/envelopes; CLI `procore audit dry-run` (default/safe) + `execute` (opt-in --confirm only); mocked tests with live isolation; JSON-first receipts (06- artifact) with full redaction; SQLite gated on migrator readiness). Reuses Prompt_04 injectable client + redaction + Prompt_05 contract + Prompt_06 mapping. See evidence 06-procore-endpoint-audit-dry-run.json. (minimal pointer, surgical).

**Prompt 09 (2026-05-28):** Pilot project dry-run sync pipeline + local SQLite apply (new procore/sync.py coordinator with mandatory Prompt_07 auditor prerequisite gate; --dry-run default produces serializable redacted plan; --apply explicit opt-in only executes GETs via Prompt_04 client then normalizes + idempotent upserts to local/temp SQLite only via additive repositories methods; receipts + redaction everywhere; incremental policy + watermarks; 100% mocked tests + temp DB isolation; CLI `procore sync --dry-run|--apply --json`. See evidence 09-procore-dry-run-sync-proof.json (full 8-section). Minimal pointer only (surgical).

**Prompt 10 (2026-05-28):** Procore Obsidian deterministic output preview (new obsidian.py + hybrid vault_writer markers for 01_Projects/ + cli/procore obsidian preview + 8 templates from Phase 03 package (shas recorded) + procore_sensitive_routing_rules.yaml + test_procore_obsidian_output.py + exports in __init__). Dry-run default, explicit --apply, redaction + yaml routing only, 100% mocked. See evidence `docs/evidence/construction-intelligence-phase-03/10-procore-obsidian-output-preview.md` (full 8-section + rendered samples + guardrails + checklists). Minimal pointer only (surgical).

**Prompt 11 (2026-05-28):** Procore CLI surface finalization + operator runbook + `procore validate` (new `procore/validate.py` read-only stack-readiness check across seeds/mapping/redaction/Obsidian templates/vault writer/schema/auth; new `docs/operations/procore-operator-runbook.md`; `obsidian preview --json` default normalized to True for parity; redacted exception envelope; 7 mocked tests). See evidence `docs/evidence/construction-intelligence-phase-03/11-procore-cli-surface-and-operator-runbook.md` (full 8-section). Minimal pointer only (surgical).
