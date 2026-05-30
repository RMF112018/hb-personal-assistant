# 10A — Controlled Decrypt Read Proof (`graph mail body show`)

Phase 06 Prompt 08A · **local-only** (vault + DB; no Graph call) · `cli/graph.py`

## Command

```
hb-assistant graph mail body show --message-id <id> --reason <reason> [--show-plaintext] [--json]
```

- `--reason` is **required** (audited locally).
- Default output is a **redacted summary** — never plaintext.
- `--show-plaintext` decrypts via `text_vault.decrypt_text(ref)` and prints to **this terminal only**
  (never to disk, log, evidence, or JSON).
- Every invocation records a local audit receipt (`email_processing_receipts`,
  `operation="body_decrypt_read"`, `detail = {reason, body_length, plaintext_emitted}`) — no plaintext.
- Unknown message id → `{"found": false}` (exit 0).

## Live redacted summary (real captured message; no plaintext)

`graph mail body show --message-id <AAkAL…> --reason validation --json`:

```json
{
  "found": true,
  "encrypted_full_body_ref_present": true,
  "body_length": 4499,
  "body_content_type": "html",
  "sensitivity_classification": "privileged_or_confidential_markers",
  "review_required": true,
  "plaintext_persisted": false,
  "encryption_method": "fernet_text_vault"
}
```

The summary carries length / content-type / sensitivity / review only — **no body content**. The synthetic
id form `--message-id synthetic-message-id --reason validation --json` returns `{"found": false}`.

## `--show-plaintext` decision

`--show-plaintext` **is implemented** (operator-only, terminal-only) but is **not exercised in evidence**:
running it would print real body plaintext to the terminal, which must never be captured. The redacted
summary above is the evidence form. The plaintext path is covered structurally by tests
(`tests/test_graph_mail_body_cli.py` asserts the default JSON contains no plaintext and an audit receipt
is recorded). This honors the prompt's allowance to keep plaintext strictly off any persisted surface.
