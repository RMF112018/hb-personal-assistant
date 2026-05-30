# 10A — Active Email Policy: Encrypted-Body Fields + Locks

Phase 06 Prompt 08A · `construction/policy/email_active.py` + `resources/config/email_intelligence_active_policy.yaml`

## New policy fields (with their lock type)

| field | type | seed value |
|---|---|---|
| `full_body_storage_allowed` | `bool` (may be true) | `true` |
| `full_body_storage_mode` | `Literal["encrypted_text_vault"]` | `encrypted_text_vault` |
| `plaintext_body_persistence_allowed` | `Literal[False]` | `false` |
| `obsidian_full_body_allowed` | `Literal[False]` | `false` |
| `evidence_full_body_allowed` | `Literal[False]` | `false` |
| `log_full_body_allowed` | `Literal[False]` | `false` |
| `attachment_content_storage_allowed` | `Literal[False]` | `false` |
| `encrypted_body_requires_review_for_sensitive` | `Literal[True]` | `true` |
| `max_full_body_fetch_per_run` | `int` (validator 1–1000) | `100` |

All pre-existing locks (`mailbox_mode==read_only`, `writeback_allowed==False`,
`mailbox_mutation_allowed==False`, `metadata_only_by_default==True`, `full_email_body_in_obsidian==False`,
…) are unchanged. `model_config = {"extra": "forbid"}` rejects unknown keys.

## Validation proof (`tests/test_email_active_policy_encrypted_body.py`)

- Seed loads with `full_body_storage_allowed True`, mode `encrypted_text_vault`,
  `plaintext_body_persistence_allowed False`, cap 100.
- Setting any of `plaintext_body_persistence_allowed`, `obsidian_full_body_allowed`,
  `evidence_full_body_allowed`, `log_full_body_allowed`, `attachment_content_storage_allowed`,
  `mailbox_mutation_allowed`, `writeback_allowed`, `full_email_body_in_obsidian` to `True` → `ValidationError`.
- `full_body_storage_mode` cannot be `plaintext`/`raw_sqlite` (Literal lock) — a broad "allow full body"
  cannot bypass the encrypted-vault mode.
- `encrypted_body_requires_review_for_sensitive` cannot be disabled.
- `max_full_body_fetch_per_run` outside 1–1000 rejected.
- Unknown fields rejected (`extra: forbid`).

The V10 `email_intelligence_active_policy` table + its `set/get_email_intelligence_active_policy`
adapter are **unchanged** — the new fields live in the Pydantic model + YAML, consumed directly by the
indexer (decoupled from the DB policy snapshot).
