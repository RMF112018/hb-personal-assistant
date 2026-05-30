# Phase 06 Operational Email Workflows (Encrypted Full-Body) Runbook

## 1. Overview

Phase 06 provides a read-only, project-aware Outlook/Exchange email intelligence workflow that:
- checks mail readiness and guardrails;
- discovers included source folders;
- discovers/indexes bounded project-relevant messages;
- captures full bodies only as encrypted local text-vault artifacts (policy gated);
- classifies and routes sensitive/low-confidence items for review;
- generates safe Obsidian projections for operator use.

Phase 06 does not:
- mutate mailbox state (no send/reply/forward/move/copy/delete);
- persist plaintext full bodies into SQLite/repo/evidence/Obsidian;
- copy attachment contents into the vault;
- perform unbounded full-mailbox backfill.

Operational scope defaults to bounded pilot workflows (for example, `tropical`, `--lookback-days 30`).

## 2. Safety Model

- Mailbox mutation allowed: `false`
- Plaintext body persistence allowed: `false`
- Encrypted full body storage: `true`
- Encryption method: `text_vault` / Fernet
- Ciphertext location: app-support `security/text-vault/*.enc`
- Key source: `HB_TEXT_VAULT_KEY` or app-support `security/text-vault.key`
- Obsidian full body storage: `false`
- Attachment content copy: `false`
- Full mailbox backfill: `false`

## 3. Daily / On-Demand Operator Workflow

Run in order:

```bash
hb-assistant graph mail status --json
hb-assistant graph mail folders --dry-run --json
hb-assistant graph mail discover --project tropical --lookback-days 30 --dry-run --json
hb-assistant graph mail index --project tropical --lookback-days 30 --include-encrypted-body --json
hb-assistant graph mail classify --project tropical --lookback-days 30 --use-encrypted-body-context --json
hb-assistant graph mail review-queue --json
hb-assistant graph mail obsidian --project tropical --include-encrypted-body-status --json
```

Notes:
- `index` defaults to `--no-dry-run`; add `--dry-run` for preview-only.
- `classify` defaults to `--dry-run`; add `--no-dry-run` to persist advisory structured output.
- `review-queue` defaults to `--dry-run`; add `--no-dry-run` to enqueue rows.
- `obsidian` defaults to `--dry-run`; add `--no-dry-run` to write marker-bounded notes.

## 4. Dry-Run Workflow

Use dry-run to validate posture without writing workflow rows/notes:

```bash
hb-assistant graph mail folders --dry-run --json
hb-assistant graph mail discover --project tropical --lookback-days 30 --dry-run --json
hb-assistant graph mail index --project tropical --lookback-days 30 --include-encrypted-body --dry-run --json
hb-assistant graph mail classify --project tropical --lookback-days 30 --use-encrypted-body-context --dry-run --json
hb-assistant graph mail review-queue --project tropical --lookback-days 30 --dry-run --json
hb-assistant graph mail obsidian --project tropical --include-encrypted-body-status --dry-run --json
```

Expected safe output characteristics:
- command envelope includes `ok` plus command status;
- no plaintext body fields are returned;
- no raw encrypted vault refs are emitted;
- no mailbox mutation activity is attempted.

## 5. Review Queue Workflow

Items route to review when deterministic or model-advisory signals indicate elevated risk, including:
- sensitivity-category matches;
- low-confidence deterministic/project match signals;
- low-confidence model classifications;
- invalid model JSON or schema rejection.

Inspect review queue:

```bash
hb-assistant graph mail review-queue --project tropical --lookback-days 30 --json
```

Handling guidance:
- keep notes decision-focused and source-linked;
- avoid copying body plaintext into any note/evidence artifact;
- use controlled body read only when required for legitimate operator review.

## 6. Controlled Body Read Workflow

Safe summary mode (default, no plaintext):

```bash
hb-assistant graph mail body show --message-id <message_id> --reason operator_review --json
```

Optional plaintext-to-terminal mode:

```bash
hb-assistant graph mail body show --message-id <message_id> --reason operator_review --show-plaintext
```

Warnings:
- terminal plaintext is transient and operator-visible only;
- do not paste plaintext into Obsidian or evidence docs;
- do not redirect plaintext output to files;
- use only for legitimate, minimal-scope operator review.

## 7. Obsidian Output

Primary output path:
- `Work/HB Personal Assistant/06_Email_Intelligence/...` in the configured Obsidian vault.

Output characteristics:
- project-level correspondence intelligence is default (not one-note-per-email);
- review-required and meeting-prep notes are grouped/sanitized;
- encrypted-body availability appears as safe status booleans/counts only;
- full body plaintext is never written.

## 8. Evidence and Audit Workflow

For closeout/audit posture checks:

```bash
python -m pytest -q --no-header
ruff check .
mypy .
python -m compileall src tests
hb-assistant graph mail status --json
hb-assistant graph mail obsidian --project tropical --include-encrypted-body-status --dry-run --json
```

Review evidence docs under:
- `docs/evidence/construction-intelligence-phase-06-email/`

Verify:
- no mutation proofs;
- no plaintext leakage proofs;
- encrypted-body storage and vault-ref proofs;
- schema/validation and routing evidence for advisory outputs.

## 9. Troubleshooting

- Missing Graph permission/token expired:
  run `hb-assistant graph mail status --json`; re-authenticate and re-check delegated scopes.
- No matching messages:
  increase `--lookback-days` or review project keyword coverage.
- Encrypted ref missing:
  re-run index with `--include-encrypted-body` and confirm policy permits capture.
- Decrypt failure / key missing:
  validate `HB_TEXT_VAULT_KEY` or app-support `security/text-vault.key` integrity.
- App-support path/DB unavailable:
  restore expected app-support directories and SQLite path.
- Obsidian output blocked:
  verify vault path and run `obsidian` with `--dry-run --json` first.
- Validation command failure:
  classify as baseline vs new regression before changing Phase 06 behavior.

## 10. Maintenance Notes for Future Agents

- Do not loosen plaintext persistence guards.
- Do not add Graph mail write endpoints to Phase 06 flow.
- Do not store body plaintext in Obsidian outputs.
- Do not copy encrypted vault blobs into the repo.
- Do not re-read unchanged files already in active context unless proof/line validation requires it.
- Reconcile all schema/policy changes against current repo truth and existing safety evidence before modifying Phase 06 contracts.
