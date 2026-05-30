# Prompt 15 — Operator Runbook and Handoff

Date: 2026-05-30

## Handoff Snapshot

- HEAD: `0586885c864361b4ec8b1b5edd64c2c2768aa03e`
- Branch: `main`
- Working tree: `?? .code-graph/` (untracked runtime artifact)
- Runbook: `docs/runbooks/phase-06-operational-email-workflows.md`

## Active CLI Workflow Surface

Authoritative chain:
- `hb-assistant graph mail status --json`
- `hb-assistant graph mail folders --dry-run --json`
- `hb-assistant graph mail discover --project tropical --lookback-days 30 --dry-run --json`
- `hb-assistant graph mail index --project tropical --lookback-days 30 --include-encrypted-body --json`
- `hb-assistant graph mail classify --project tropical --lookback-days 30 --use-encrypted-body-context --json`
- `hb-assistant graph mail review-queue --json`
- `hb-assistant graph mail obsidian --project tropical --include-encrypted-body-status --json`
- `hb-assistant graph mail body show --message-id <message_id> --reason operator_review --json`

Command/help conformance checked for:
- `graph mail --help`
- `status`, `folders`, `discover`, `index`, `classify`, `review-queue`, `obsidian`
- `graph mail body show --help`

## Policy Posture (Operational)

- mailbox mutation allowed: `false`
- plaintext body persistence allowed: `false`
- encrypted full body storage: `true`
- encryption method: `text_vault` / Fernet
- ciphertext at rest: app-support `security/text-vault/*.enc`
- key source: `HB_TEXT_VAULT_KEY` or app-support `security/text-vault.key`
- Obsidian plaintext body storage: `false`
- attachment content copy: `false`
- full mailbox backfill: `false`

## Validation Matrix (Prompt 15 Required)

Executed commands and exact outcomes:

1. `python -m pytest -q --no-header` → **failed**
- 14 failures; remainder passed/skipped.
- Failures observed in:
  - `tests/test_automation.py` (weekend/manual-only orchestration expectations)
  - `tests/test_email_classifier.py` and `tests/test_email_model_classifications_schema_v14.py` (`ConstructionStore` missing `upsert/get/list_email_model_classification` methods)
  - `tests/test_graph_mail_cli.py` (`graph mail status` payload keys absent when login endpoint DNS fails)

2. `ruff check .` → **passed** (`All checks passed!`)

3. `mypy .` → **failed**
- 32 errors in 6 files (typed-test indexing/type mismatch plus missing `ConstructionStore` email model classification methods).

4. `python -m compileall src tests` → **passed**

5. `hb-assistant graph mail status --json` → **failed**
- `status_error`
- reason: `login.microsoftonline.com` DNS/endpoint resolution failure in this environment.

6. `hb-assistant graph mail obsidian --project tropical --include-encrypted-body-status --dry-run --json` → **failed**
- `obsidian_error`
- reason: local app DB unavailable at `/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`.

## Evidence Index (Prompt 11–14 + Safety)

Key references:
- `docs/evidence/construction-intelligence-phase-06-email/11-ollama-structured-email-intelligence-encrypted-body-context.md`
- `docs/evidence/construction-intelligence-phase-06-email/12-obsidian-email-output-no-plaintext-body-proof.md`
- `docs/evidence/construction-intelligence-phase-06-email/13-operational-workflow-pilot-index-proof.md`
- `docs/evidence/construction-intelligence-phase-06-email/13-operational-workflow-encrypted-body-proof.md`
- `docs/evidence/construction-intelligence-phase-06-email/13-operational-review-queue-proof.md`
- `docs/evidence/construction-intelligence-phase-06-email/13-operational-obsidian-preview.md`
- `docs/evidence/construction-intelligence-phase-06-email/no-mailbox-mutation-proof.md`
- `docs/evidence/construction-intelligence-phase-06-email/14-no-plaintext-body-leakage-proof.md`
- `docs/evidence/construction-intelligence-phase-06-email/14-encrypted-body-storage-closeout-proof.md`
- `docs/evidence/construction-intelligence-phase-06-email/14-final-validation-closeout.md`

## Known Limitations and Deferred Items

- Live Graph/runtime attestation is environment-limited when Microsoft endpoint resolution is unavailable.
- Local DB-dependent commands fail when app-support SQLite is missing/unavailable.
- Existing repo baseline failures remain in test/type suites outside Prompt 15 documentation scope.

## Final Operational Status for Handoff

Phase 06 remains **conditionally operational** for handoff:
- command chain, safety guardrails, encrypted-at-rest model, and documentation are in place;
- full production attestation requires rerun on a live-local environment with:
  - valid Microsoft auth and endpoint reachability,
  - available app-support SQLite path,
  - normal project data presence.

Prompt 15 completion criteria met via:
- operator runbook publication,
- command/help-conformant workflow documentation,
- explicit safety model and plaintext precautions,
- maintenance constraints for future local agents,
- final handoff summary with validation outcomes and attestation boundary.
