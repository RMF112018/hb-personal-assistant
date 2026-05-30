# 17 — Operational Email Intelligence (Phase 06)

Status: **in progress** · Phase 06 Prompts 00–02 landed · Migration **V10** (Prompt 02)

Phase 06 turns the Phase 02 *deferred* email intelligence into operational, **read-only**,
project-aware email workflows over the existing GET-only Graph stack. It is local-first: SQLite is
the operational index, Obsidian output is summary/manifest/receipt-level, and the mailbox is never
mutated. The full operational pipeline (folder discovery → bounded discovery → metadata index →
project match → relationship candidates → review routing → summaries/meeting-prep → Obsidian) is
built across later prompts; this record covers the foundation landed so far.

## Prompts 00–01 (foundation)

- **Prompt 00** — repo-truth rebaseline + mail-permission readiness (`419890a`). Confirmed the
  GET-only `GraphHttpClient`/`MailClient`, the `Mail.Read`-only runtime scope (grant-but-suppress),
  and the four-layer mailbox read-only enforcement.
- **Prompt 01** — official Graph mail endpoint contract (`dadd9c1`). Repo-native YAML at
  `resources/config/graph_mail_read_endpoint_allowlist.yaml` (GET-only paths, `Prefer:
  IdType="ImmutableId"`, body-free message `$select`, attachment `$select` that **excludes
  `contentBytes`**, paging discipline) and `graph_mail_mutation_endpoint_blocklist.yaml`.

## Prompt 02 — active policy + mailbox source registry (Migration V10)

Activates email intelligence **alongside** the preserved Phase 02 deferred policy.

- **Active policy** — `construction/policy/email_active.py` (`EmailIntelligenceActivePolicy`,
  `load_email_intelligence_active_policy`) + seed `resources/config/email_intelligence_active_policy.yaml`.
  Pydantic `Literal` locks: `mailbox_mode=='read_only'`, writeback/mutation/full-archive/
  source-copy/full-body-in-obsidian/attachment-content-download all `False`, metadata-only,
  review-required-for-sensitive, `initial_backfill_mode=='pilot_projects_only'`,
  invalid-JSON→review; bounded `default_lookback_days` (1–366).
- **Mailbox source registry** — `construction/policy/mailbox_registry.py` (`MailboxFolderSource`,
  `MailboxSourceRegistry`, `build_mailbox_source_registry`). Derives included (Inbox/Sent Items/
  Archive) and excluded (Deleted Items/Junk Email/Drafts) folder source rows from the active policy.
  The mailbox owner is stored only as a sha256 hash; `folder_id` is resolved later by live discovery.
- **Schema (V10, additive)** — two `email_*` tables: `email_intelligence_active_policy` (singleton)
  and `email_source_locations`, both with `CHECK` constraints locking the read-only / no-mutation /
  no-full-body / no-source-copy / no-attachment-download / metadata-only / pilot-only-backfill flags.
  V1–V9 and the V5 `construction_email_intelligence_deferred_state` row are untouched (preserved
  historical evidence). The package's remaining operational tables are **Prompt 03 (V11)**.
- **Store adapter** — `ConstructionStore.set/get_email_intelligence_active_policy` and
  `upsert/get/list_email_source_location`, each raising `ValueError` on a lock violation before SQL.

### Four-layer read-only lock (defense in depth)

1. **Model** — Pydantic `Literal` (raises `ValidationError`).
2. **Adapter** — `ValueError` before SQL.
3. **Database** — SQLite `CHECK` (raises `IntegrityError`).
4. **Scope** — runtime requests `Mail.Read` only.

Naming reconciliation: new operational email tables use the package's `email_*` family (Prompt 03
extends it); the active policy lives beside the deferred one in `construction/policy/` rather than a
new `email_intelligence/` package (which may emerge as later modules land). Evidence:
`docs/evidence/construction-intelligence-phase-06-email/` (`00`/`01`/`02` numbered docs,
`mail-permission-readiness-proof.md`, `mailbox-source-registry-proof.md`,
`mailbox-readonly-guardrail-proof.md`, and the endpoint-contract research doc).
