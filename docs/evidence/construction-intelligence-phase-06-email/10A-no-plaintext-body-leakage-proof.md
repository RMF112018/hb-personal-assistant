# 10A — No Plaintext Body Leakage Proof

Phase 06 Prompt 08A · full bodies are encrypted at rest; plaintext lives nowhere persisted

## SQLite — no plaintext-body column anywhere

Live operational DB scan of all 14 `email_*` tables for plaintext-body columns
(`body_plaintext` / `raw_body` / `body_html` / `body_content` / `body_text` / `body` / `content`):
**NONE**. The encrypted-body row stores only `encrypted_full_body_ref` + `body_hash` + `body_length`
+ `body_content_type`; `email_messages` keeps only the pre-existing bounded, redacted
`body_preview_excerpt_redacted` (≤120 chars) and its `full_body_persisted = 0` CHECK. Asserted by
`tests/test_email_body_security.py::test_no_plaintext_body_column_in_any_email_table`.

## Encrypted blobs are not plaintext

Each captured body's vault blob (`security/text-vault/{ref}.enc`, outside the repo, `0o600`) is Fernet
ciphertext — the synthetic round-trip test confirms the plaintext bytes are absent from the blob, and
the live capture shows `plaintext_persisted = 0` for every row.

## CLI JSON / evidence / logs

- `index … --include-encrypted-body --json` emits only counts/flags (`bodies_encrypted`,
  `vault_blob_written`, `plaintext_persisted: false`) — no body text.
- `body show … --json` emits a redacted summary (length, hash prefix, content-type, sensitivity, review)
  — no body text; `--show-plaintext` (terminal-only) is never run in evidence.
- This evidence set carries refs (sha256 hashes), integer lengths, content-types, and sensitivity
  category names only. (Evidence files mention forbidden column names like `raw_body` solely to document
  their absence; `tests/test_email_body_security.py` flags only decrypted-plaintext markers.)

## Source modules

Static scan of `construction/email/*.py` + `cli/graph.py` + the read client/guard finds no
`body_plaintext` / `raw_body` / `body_html` / `full_body_in_obsidian` tokens and no write-verb calls
(`tests/test_email_body_security.py`).
