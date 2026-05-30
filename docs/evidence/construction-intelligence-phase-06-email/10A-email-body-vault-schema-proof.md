# 10A — Encrypted-Body Vault Schema Proof (Migration V12)

Phase 06 Prompt 08A · additive Migration **V12** · `store/migrator.py`

## Migration version

`SQLiteMigrator.apply()` on a fresh DB returns **12**. V1–V11 are untouched; the V11
`email_messages.full_body_persisted = 0` CHECK is preserved (the body never lives as plaintext in
email_messages or any SQLite table — it lives encrypted in the text vault, referenced by this side
table).

## Schema (`email_message_body_vault_refs`)

```sql
CREATE TABLE IF NOT EXISTS email_message_body_vault_refs (
  message_id TEXT PRIMARY KEY REFERENCES email_messages(message_id) ON DELETE CASCADE,
  internet_message_id TEXT,
  conversation_id TEXT,
  body_content_type TEXT,
  body_hash TEXT NOT NULL,
  body_length INTEGER NOT NULL,
  encrypted_full_body_ref TEXT NOT NULL,
  encrypted_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  encryption_method TEXT NOT NULL DEFAULT 'fernet_text_vault',
  plaintext_persisted INTEGER NOT NULL DEFAULT 0 CHECK(plaintext_persisted = 0),
  obsidian_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(obsidian_body_persisted = 0),
  evidence_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(evidence_body_persisted = 0),
  log_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(log_body_persisted = 0),
  extraction_policy TEXT NOT NULL,
  review_required INTEGER NOT NULL DEFAULT 0,
  sensitivity_classification TEXT,
  created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

There is **no** plaintext-body column (`body_plaintext` / `raw_body` / `body_html` / `body_content` /
`body_text` / `body` / `content` are all absent — asserted in `tests/test_email_body_security.py`).

## CHECK-constraint reject proof (`tests/test_email_body_vault.py`)

Inserting `1` into any of `plaintext_persisted`, `obsidian_body_persisted`, `evidence_body_persisted`,
`log_body_persisted` → `sqlite3.IntegrityError` (parametrized test, all four pass).

## Ref-only insert proof

`upsert_email_body_vault_ref(...)` stores only the ref + hash + length + content type + policy + review
+ sensitivity. It rejects an empty `encrypted_full_body_ref`, empty `body_hash`, and `body_length <= 0`
(no plaintext parameter exists), and is idempotent on `message_id` (re-upsert keeps one row).
`get_email_body_vault_ref` returns the metadata, never plaintext.
