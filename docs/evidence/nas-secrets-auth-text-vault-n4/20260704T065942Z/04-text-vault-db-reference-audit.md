# 04 — Text Vault DB-Reference Audit

Derived from the sha-verified local copy, opened `mode=ro` (never the NAS DB; see 01 linkage + 09 write-safety).
No ref strings, no decrypted content printed — counts and column names only.

## Reference columns (repo-truth: `src/hb_assistant/security/text_vault.py`, migrator)
Each ref = `sha256(plaintext)[:32]`, mapping to `<app-support>/security/text-vault/<ref>.enc`.

| Table | Column | Non-null rows | Notes |
|---|---|---|---|
| `procore_text_intelligence` | `encrypted_full_text_ref` | 12,779 | writer `procore_enrichment.py` |
| `email_message_body_vault_refs` | `encrypted_full_body_ref` | 5 | `encryption_method='fernet_text_vault'`; keyed by message_id |
| `source_intelligence_text` | `text_vault_ref` | 0 (all NULL) | column exists, unused in this DB |
| **Distinct union** | — | **7,198 distinct refs** | 12,779 rows collapse to fewer refs (content-addressed dedupe) |

## Plaintext-never-persisted invariant (raises migration stakes)
Schema `CHECK(...=0)` guards ensure bodies are NOT stored in the DB (`raw_body_persisted=0`, and for email
`plaintext/obsidian/evidence/log_body_persisted=0`). ⇒ the `.enc` blob is the **only** copy of each body; losing
the key or blobs is unrecoverable, and nothing in the DB can substitute.

## Implication
The copied DB references 7,198 distinct vault entries. For any decrypt-capable runtime on the NAS, the key + the
matching blobs must be present (see 05). Absent them, those bodies are unreadable.
