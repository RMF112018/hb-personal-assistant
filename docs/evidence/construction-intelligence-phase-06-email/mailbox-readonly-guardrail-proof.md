# Mailbox Read-only Guardrail Proof (Phase 06 / Prompt 02)

**Generated:** 2026-05-29 (audit run)
**Claim:** Read-only is locked for the active email policy and mailbox source registry at the
**model**, **store-adapter**, and **database** layers — defense in depth, mirroring the existing
deferred-policy pattern — plus the standing `Mail.Read`-only runtime scope.

---

## 1. Four-layer lock matrix (with real outputs)

### Layer A — Model (Pydantic `Literal`)
`EmailIntelligenceActivePolicy` and `MailboxFolderSource` lock the guardrail fields with
`Literal[...]`; loosening any of them raises `ValidationError`:

```text
EmailIntelligenceActivePolicy(... mailbox_mutation_allowed=True) →
  ValidationError: Input should be False
```
Locked policy fields: `mailbox_mode=="read_only"`, `writeback_allowed=False`,
`mailbox_mutation_allowed=False`, `full_archive_crawl=False`, `source_copy_to_vault=False`,
`full_email_body_in_obsidian=False`, `attachment_content_download_by_default=False`,
`metadata_only_by_default=True`, `review_required_for_sensitive=True`,
`initial_backfill_mode=="pilot_projects_only"`, `ollama_invalid_json_routes_to_review=True`.
Locked folder-source fields: `read_only=True`, `mailbox_mutation_allowed=False`,
`full_archive_crawl_allowed=False`, `source_copy_to_vault_allowed=False`,
`full_email_body_in_obsidian_allowed=False`. `model_config = {"extra": "forbid"}`.

### Layer B — Store adapter (`ValueError` before SQL)
The adapter methods reject violations before any SQL executes:

```text
store.set_email_intelligence_active_policy(... writeback_allowed=True) →
  ValueError: writeback_allowed must be False — Phase 06 email intelligence is read-only and metadata-only
store.upsert_email_source_location(... read_only=False) →
  ValueError: email_source_locations.read_only must be True (no mailbox writeback)
```

### Layer C — Database (SQLite `CHECK`)
Even if the adapter were bypassed, the V10 schema `CHECK` constraints reject the write:

```text
INSERT INTO email_source_locations (... mailbox_mutation_allowed) VALUES (...,1) →
  sqlite3.IntegrityError: CHECK constraint failed: mailbox_mutation_allowed = 0
```
CHECK-locked columns — `email_intelligence_active_policy`: `mailbox_mode='read_only'`,
`writeback_allowed=0`, `mailbox_mutation_allowed=0`, `full_archive_crawl=0`,
`source_copy_to_vault=0`, `full_email_body_in_obsidian=0`,
`attachment_content_download_by_default=0`, `metadata_only_by_default=1`,
`review_required_for_sensitive=1`, `initial_backfill_mode='pilot_projects_only'`,
`ollama_invalid_json_routes_to_review=1`. `email_source_locations`: `read_only=1`,
`mailbox_mutation_allowed=0`, `full_archive_crawl_allowed=0`, `source_copy_to_vault_allowed=0`,
`full_email_body_in_obsidian_allowed=0`.

### Layer D — Runtime scope (unchanged)
Config `identity.delegated_scopes` requests `Mail.Read` only; `Mail.ReadWrite`/`Mail.ReadWrite.All`/
`Mail.Send` are never requested (proven in Prompt 00 `mail-permission-readiness-proof.md`). The
existing `tests/test_mutation_lockout.py` static scan confirms no Graph write APIs exist.

## 2. No mutation / full-body / attachment-download path exists

- The Graph client surface remains GET-only (Prompt 01 contract); no method writes mail.
- `full_email_body_in_obsidian` and `attachment_content_download_by_default` are locked `False`
  at all three layers; the active policy never enables full-body persistence or attachment-content
  download.
- `initial_backfill_mode` is locked to `pilot_projects_only` and `default_lookback_days` is
  bounded (1–366) → no full-mailbox backfill.

## 3. Test coverage

```text
tests/test_email_active_policy.py           — model locks reject all 11 loosenings + unknown field + bounds
tests/test_email_mailbox_registry.py        — folder-source locks; owner hashed; deterministic build
tests/test_email_registry_migration_v10.py  — SQL CHECK IntegrityError (6+2 cases); adapter ValueError (11+5 cases);
                                               round-trip persist; idempotent V10; V1-V9 + deferred table preserved
```
Result: **137 passed** (targeted) · ruff clean · mypy clean (117 files) · full safe subset **1311 passed**.

**No stop condition triggered** — additive V10 only; no mutation path, no write scope, no full-body
default persistence, no attachment-content default download.
