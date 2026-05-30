# 10A — Email Body Encryption Proof

Phase 06 Prompt 08A · reuses `hb_assistant.security.text_vault` (Fernet) · **no email body plaintext in this evidence**

## Synthetic encryption mechanism (test-proven)

Using **synthetic text only** (`tests/test_email_body_vault.py::test_vault_round_trip_with_synthetic_text`):

- `encrypt_text("Synthetic non-sensitive body text for testing only.")` returns a deterministic ref
  (`sha256(text)[:32]`); re-encrypting the same text returns the **same** ref.
- The blob is written **outside the repo** under Application Support
  `security/text-vault/{ref}.enc`, with file mode **`0o600`**; the key file
  `security/text-vault.key` is `0o600` (see `tests/test_text_vault.py`).
- The ciphertext blob does **not** contain the plaintext bytes.
- `decrypt_text(ref)` round-trips back to the synthetic plaintext.
- SQLite stores only the ref + `body_hash` + `body_length` + content-type + policy (no plaintext column).

## Live capture (real bodies — counts/metadata only, never plaintext)

`hb-assistant graph mail index --project tropical --lookback-days 30 --include-encrypted-body --max-messages 2 --json`
(read-only Graph fetch → encrypt → discard plaintext): **`bodies_encrypted: 5`**, `vault_blob_written: true`,
`plaintext_persisted: false`. Read-only inspection of `email_message_body_vault_refs` afterward (refs are
sha256 hashes, lengths are integers — no body content):

```
vault ref rows: 5   (all plaintext_persisted = 0)
  ref=9b09e20f09be…  len=20979  type=html  sens=privileged_or_confidential_markers  review=1  blob 0o600
  ref=b7e8b7d071c7…  len=33906  type=html  sens=legal_correspondence                review=1  blob 0o600
  ref=1c86ab39a85f…  len=1689   type=html  sens=None                                 review=0  blob 0o600
  ref=1f4a50f6afcf…  len=44921  type=html  sens=legal_correspondence                review=1  blob 0o600
  ref=cafa3358fa41…  len=4499   type=html  sens=privileged_or_confidential_markers  review=1  blob 0o600
```

Every encrypted blob exists outside the repo with `0o600` perms; every row has `plaintext_persisted=0`;
sensitive bodies (legal / privileged) carry `review_required=1`. No body content appears in the DB, the
CLI JSON, or this evidence.

## Dry-run eligibility (no fetch, no blob)

`index … --include-encrypted-body --dry-run --json` → see
[`10A-email-body-indexing-dry-run.json`](./10A-email-body-indexing-dry-run.json): `body_capture_enabled:
true`, `bodies_eligible: 100` (capped from 402 messages by `max_full_body_fetch_per_run`),
`bodies_encrypted: 0`, `vault_blob_written: false`, `plaintext_persisted: false` — proving what *would*
happen without fetching any body or writing any blob.
