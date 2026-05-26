# Remediation: Morning Run Orchestration Upgrade (Phase 14 Prompt 07)

## Summary
Phase 14 Prompt 07 upgrades the `hb-assistant run morning` surface to execute the complete local work-product intelligence pipeline while correctly classifying Graph consent blockers.

It implements the exact stage model, status values, JSON contract, and failure-isolation rules defined in `05_Local_Runtime_Orchestration_Specification.md` inside `MorningRunOrchestrator.run()` (and thin support in the CLI wrapper).

- Full 05 stages now executed in order (path_readiness → store_readiness → graph_auth_status → graph_retrieval → local_signal_load → classification → action_extraction → workstream_context → file_ingestion_preview → brief_generation → obsidian_write → evidence_write → run_ledger_finish).
- Early `graph_auth_status` stage probes delegated token + consent (reusing P05 patterns); Graph-dependent stages (graph_retrieval) receive `skipped_external_admin_consent` or `skipped_no_token` while *all local stages continue to success* with structured 05 statuses.
- P02–P06 capabilities are wired in: action extraction (P02/P04 with stable_keys + signals), workstream context (P05), brief generation + obsidian write with provenance (P06 generator + writer, dry_run + record_link), file preview, ledger, and sanitized evidence.
- Existing per-stage try/except + "skipped" + reason isolation pattern is preserved and mapped to the 05 status vocabulary.
- Top-level evidence and CLI JSON exactly match the 05 contract (including `"blocker_classification"`, full `"stages"` array with status/reason/counts, outputs, safety notes).
- Local stages succeed and report structured status even when Graph consent is pending (core acceptance criterion and truthful blocker posture from P01/P05).

Failure isolation is explicit: foundational blockers (paths, DB, schema, evidence) stop the run; non-foundational (Graph no-token/consent, individual stage failures) are isolated.

All changes surgical, redacted, dry-run-first, extending the patterns already present in the partial Phase 12 orchestrator.

## Files Updated
- `src/hb_assistant/automation/orchestrator.py` — primary: extended `run()` to the full 05 stage list and logic; added `graph_auth_status` classification (reusing P05 classifier/proof patterns); wired P02–P06 services (ActionService/extractor for action_extraction, WorkstreamContextBuilder, DailyBriefGenerator + MarkerBoundedWriter for brief_generation + obsidian_write with dry_run + P06 provenance, FileIngestionService); preserved/extended ledger (`_record_run`/`_finish_run`), `_write_evidence`, per-stage try/except isolation, weekend/catch-up gates; ensured top-level payload matches 05 JSON contract exactly.
- `src/hb_assistant/cli/run.py` — minimal: pass-through/enhancement of richer orchestrator result into the CLI JSON payload for `--dry-run --json`; preserved the existing `StoreReadinessError` special-case handling with its minimal stages list.
- `tests/test_automation.py` (and/or `test_cli_canonical.py`) — new/extended tests covering no-token/consent-blocked paths (Graph stages skipped with correct statuses, local stages succeed), DB blocked (`StoreReadinessError`), dry-run vs apply, isolated non-foundational failure, full 05 JSON contract match. Reused P03-style temp DB + fixture patterns.
- New: `docs/evidence/phase-14-local-runtime-workstream-intelligence/prompt-07/` (full evidence package with live `run morning --dry-run --json` showing stages + blocker_classification, test results, etc.).
- New: `docs/architecture/remediation-morning-run-orchestration-upgrade.md` (this note).
- Updated: `docs/architecture/00-README.md` (P07 index entry under Phase 14 workstream intelligence, matching P01/P03/P04/P06 style).

## Key Changes
- The orchestrator is now the single source of truth for the 05 stage model and blocker classification.
- Graph consent is treated as a non-fatal, non-foundational blocker: stages are explicitly skipped with the correct 05 status while the local pipeline (actions, context, brief with P06 provenance, files, ledger, evidence) runs to completion.
- P06 obsidian provenance (written_to_note, stable_key task comments, would-link dry-run reporting) is exercised in the `obsidian_write` stage.
- All prior ledger, evidence sanitization, isolation, and dry-run safety guarantees are preserved and extended.
- CLI surface (`hb-assistant run morning --dry-run --json`) now surfaces the full structured 05 output for validation and automation consumers.
- Tests provide repeatable proof of the blocker-classification + local-continuation behavior and the exact JSON contract.

## Validation Performed
- New automation/run orchestration tests (no-token/consent-blocked, DB blocked, dry-run, isolated failure, full 05 JSON contract): green.
- `hb-assistant run morning --dry-run --json`: emits full 05 stages array + `"blocker_classification"` (Graph stages correctly skipped, local stages succeed with structured statuses); zero mutation.
- Full verification suite: pytest (automation/run focused + relevant), ruff, mypy (automation + cli/run), `diagnostics scan-sensitive --json` (clean, exit 0), `run morning --dry-run --json`.
- Sensitive scan clean.
- Commit: `feat(run): orchestrate full local morning workflow`

## References
- `docs/plans/ph-14-workstream-Intelligence/05_Local_Runtime_Orchestration_Specification.md` (authoritative stage model, statuses, JSON contract, failure isolation rules).
- `docs/plans/ph-14-workstream-Intelligence/prompts/Prompt_07_Morning_Run_Orchestration_Upgrade.md` (P07 requirements, validation, acceptance, evidence).
- Prior Phase 14 prompts 01–06 evidence (P01/P05 blocker taxonomy + delegated proof patterns; P02–P04 actions/signals/persistence; P06 obsidian provenance + writer ready for obsidian_write stage).
- `docs/evidence/phase-14-local-runtime-workstream-intelligence/prompt-07/summary.md` (complete package + final SHA).
- `docs/architecture/00-README.md` (Phase 14 workstream intelligence index + P07 entry).
- Current partial implementation (pre-P07): `src/hb_assistant/automation/orchestrator.py` (limited stages + isolation skeleton) and `src/hb_assistant/cli/run.py` (thin morning wrapper + StoreReadinessError handling).

**Status**: `run morning` now executes the full local pipeline with truthful Graph consent blocker classification and structured 05 reporting. Local stages succeed while Graph consent is pending. Ready for P08+ (deterministic evidence harness and CI).