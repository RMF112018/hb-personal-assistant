# Prompt 11 — Ollama Structured Email Intelligence with Encrypted Body Context

Date: 2026-05-30

## What Changed

- Updated `EmailIntelligenceClassifier` so live model calls use the same bounded, in-memory prompt that may include decrypted body context when `--use-encrypted-body-context` is enabled.
- Kept decrypt flow controlled and temporary: decrypt vault ref, build prompt, call model, discard prompt/plaintext, persist only structured advisory fields.
- Kept strict invalid JSON behavior: reject output, mark `invalid_model_output`, route to review, no partial model payload persistence.
- Updated CLI `graph mail classify` client-init policy so dry-run can execute model inference when enabled by policy.
- Added Prompt 11 email structured-output schema at `resources/schemas/ollama_email_intelligence.schema.json` with strict required keys, `additionalProperties: false`, and explicit forbidden top-level fields.
- Added tests for:
  - live prompt includes decrypted body context in-memory path;
  - dry-run classify initializes model client path;
  - no plaintext leakage changes.

## Safety Proof Points

- No plaintext persistence paths were added.
- Existing V14 advisory persistence boundaries are unchanged: no raw prompt/response/plaintext body write paths.
- Mailbox mutation behavior remains unchanged (no Graph write operations introduced).
- CLI/JSON outputs remain evidence-safe and do not include decrypted body content.

## Validation Results

See `docs/evidence/construction-intelligence-phase-06-email/email-structured-output-test-results.json`.

Key outcomes:

- `ruff check .` passed.
- `python -m compileall src tests` passed.
- Full `pytest` and `mypy` runs reported existing workspace baseline issues unrelated to this prompt’s code path.
- `hb-assistant graph mail classify ... --dry-run --json` returned a safe error envelope in this environment because the operational DB path was unavailable.

## Prompt 11 Criteria Status

- Encrypted body context used only via controlled `decrypt_text` in-memory path: implemented.
- Structured output contract strictness: implemented via runtime validator + Prompt 11 schema file.
- Invalid JSON rejected with review routing: implemented.
- No plaintext body persistence or emission: preserved.
- Sensitive/low-confidence review routing with deterministic precedence: preserved.
