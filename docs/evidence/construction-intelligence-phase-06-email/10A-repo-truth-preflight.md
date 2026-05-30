# 10A — Repo-Truth Preflight (encrypted full email body storage)

Phase 06 Prompt 08A · read-only mailbox · posture change: encrypted-at-rest body capture

## Repo state before edits

- **Branch:** `main`
- **HEAD:** `89c11f4f784c6bafaa011418d0f35460071bcbbc` (Prompt 08 — attachment metadata + source-link & review candidates)
- **Working tree (clean of unrelated user changes):** only the 3 long-standing regenerated evidence
  artifacts and an untracked `.code-graph/` were present — none are user edits that this prompt would
  overwrite:
  ```
   M docs/evidence/mvp-local-runtime/outputs/06-harness-success.marker
   M docs/evidence/mvp-local-runtime/outputs/scan-sensitive.json
   M docs/evidence/remediation/prompt-05-delegated-graph-proof/summary.json
  ?? .code-graph/
  ```
  Proceeding is safe (these have been excluded from every Phase 06 commit).

## Phase 06 files found locally

- `src/hb_assistant/construction/policy/email_active.py` — **present** (`EmailIntelligenceActivePolicy`
  + `load_email_intelligence_active_policy`).
- `resources/config/email_intelligence_active_policy.yaml` — **present** (active policy seed).
- `src/hb_assistant/construction/email/` — `attachment_analyzer.py`, `folder_discovery.py`,
  `message_indexer.py`, `project_discovery.py`, `project_matcher.py`, `__init__.py`.
- `src/hb_assistant/construction/store/repositories.py`, `src/hb_assistant/store/migrator.py` (max
  migration **V11**), `src/hb_assistant/cli/graph.py`, `src/hb_assistant/graph/mail_readonly_client.py`,
  `src/hb_assistant/graph/mail_endpoint_guard.py`, `resources/config/graph_mail_read_endpoint_allowlist.yaml`.
- Encryption vault: `src/hb_assistant/security/text_vault.py` — **present** (`encrypt_text`/`decrypt_text`,
  Fernet, blobs `0o600` under Application Support `security/text-vault/`, key via `HB_TEXT_VAULT_KEY` or
  `security/text-vault.key`).

## Current full-body persistence posture (before this prompt)

- Active policy (`email_active.py` / YAML): `metadata_only_by_default: true`,
  `full_email_body_in_obsidian: false`, `attachment_content_download_by_default: false` — **no full body
  persistence**; bounded lookback; pilot-only backfill.
- DB constraint: `email_messages.full_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(full_body_persisted = 0)`
  (V11) — email_messages may **never** carry a plaintext body. The indexer (Prompt 06) stores only a
  bounded redacted `body_preview_excerpt_redacted` + hashes.

## Planned change (this prompt)

Allow **encrypted** full body capture only: bodies are fetched via the existing read-only Graph path,
encrypted immediately with `text_vault`, and only an `encrypted_full_body_ref` + hash/length/metadata are
stored in a **new side table** `email_message_body_vault_refs` (Migration V12). The
`email_messages.full_body_persisted = 0` CHECK is **preserved** — no plaintext body is ever stored in
email_messages or any SQLite table. Plaintext is never written to SQLite, Obsidian, evidence, logs,
receipts, or CLI output, and the mailbox stays strictly read-only.
