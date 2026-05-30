# Mailbox Source Registry Proof (Phase 06 / Prompt 02)

**Generated:** 2026-05-29 (audit run)
**Scope:** Represent Bobby's mailbox and its included/excluded Outlook folders as read-only
source rows, derived deterministically from the active email policy. No Graph call is made;
no raw email address is stored (owner is hashed); no mailbox mutation occurs.

---

## 1. What was added

| Layer | Artifact |
| --- | --- |
| Active policy (model + loader) | `src/hb_assistant/construction/policy/email_active.py` |
| Registry representation | `src/hb_assistant/construction/policy/mailbox_registry.py` (`MailboxFolderSource`, `MailboxSourceRegistry`, `build_mailbox_source_registry`) |
| Seed | `resources/config/email_intelligence_active_policy.yaml` |
| DB tables (V10, additive) | `email_intelligence_active_policy`, `email_source_locations` |
| Store adapter | `ConstructionStore.set/get_email_intelligence_active_policy`, `upsert/get/list_email_source_location` |

The new operational email tables use the package's `email_*` family (Prompt 03 extends it);
the historical `construction_email_intelligence_deferred_state` table is **preserved untouched**.

## 2. Registry built from the active policy (redacted owner)

`build_mailbox_source_registry(policy, mailbox_owner="bobby@example.com")` →

```text
owner_hash: 115f4e20f1ac56f4          # sha256 prefix — raw address never stored
  inbox     include=1  Inbox          -> outlook:115f4e20f1ac56f4:inbox
  sent      include=1  Sent Items     -> outlook:115f4e20f1ac56f4:sent-items
  archive   include=1  Archive        -> outlook:115f4e20f1ac56f4:archive
  excluded  include=0  Deleted Items  -> outlook:115f4e20f1ac56f4:deleted-items
  excluded  include=0  Junk Email     -> outlook:115f4e20f1ac56f4:junk-email
  excluded  include=0  Drafts         -> outlook:115f4e20f1ac56f4:drafts
```

- **Included** (`include_in_sync=1`): Inbox, Sent Items, Archive — mapped to canonical roles.
- **Excluded** (`include_in_sync=0`, role `excluded`): Deleted Items, Junk Email, Drafts.
- `folder_id` is `None` until live folder discovery (Prompt 05) — this is the metadata-only
  representation, not a live crawl.

## 3. Persisted to SQLite (read-only locks enforced)

After persisting the registry rows + the active-policy singleton via the store adapter:

```text
included folders persisted: 3
excluded folders persisted: 3
persisted active-policy row:
  mailbox_mode               = read_only
  writeback_allowed          = false
  mailbox_mutation_allowed   = false
  metadata_only_by_default   = true
  initial_backfill_mode      = pilot_projects_only
  default_lookback_days      = 30
```

## 4. Historical deferred evidence preserved

```text
construction_email_intelligence_deferred_state present: True
max schema version: 10
```

The V10 migration is strictly additive (`CREATE TABLE IF NOT EXISTS` + indexes only). The Phase 02
deferred policy module, its seed, and its V5 state row are unchanged — the active policy is a
sibling, not a replacement.

## 5. Validation

```text
pytest tests/test_email_active_policy.py tests/test_email_mailbox_registry.py \
       tests/test_email_registry_migration_v10.py … = 137 passed
ruff check .  → All checks passed!
mypy src      → Success: no issues found in 117 source files
full safe subset → 1311 passed, 1 skipped, 1 deselected
```

See `mailbox-readonly-guardrail-proof.md` for the layer-by-layer lock proof and
`02-mailbox-policy-and-threat-model.md` for the active-vs-deferred policy relationship.

**No stop condition triggered** — no mutation path, no `Mail.ReadWrite`/`Mail.Send` scope, no
destructive migration (additive V10), no full-body persistence, no attachment-content download.
