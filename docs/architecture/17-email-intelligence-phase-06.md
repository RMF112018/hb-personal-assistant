# 17 — Operational Email Intelligence (Phase 06)

Status: **in progress** · Phase 06 Prompts 00–04 landed · Migration **V11** (Prompt 03) · read-only mail client + endpoint guard (Prompt 04)

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

## Prompt 03 — operational email data schema (Migration V11)

Adds the read-only, metadata-only **data plane** the pipeline writes to, on top of the V10 policy +
source registry. The package SQL re-declared `email_source_locations` (already identical in V10);
V11 adds only the **10 new tables** and references the existing V10 table via foreign keys —
additive `CREATE TABLE IF NOT EXISTS` only, V1–V10 and the V5 deferred-state row untouched.

- **Tables (V11)** — `email_sync_state` (per-folder bounded-lookback cursor), `email_crawl_runs`
  (run receipts), `email_messages` (message **metadata**; no full body — only a bounded redacted
  `body_preview_excerpt_redacted` + hash), `email_message_recipients` (hashed addresses),
  `email_message_attachments` (metadata only), `email_project_matches`,
  `email_relationship_candidates` (cross-system link candidates), `email_thread_summaries`,
  `email_review_queue`, `email_processing_receipts`. CHECK constraints lock
  `full_body_persisted=0` / `mailbox_mutation_*=0` / `attachment_content_downloaded=0` /
  `content_downloaded=0` / `metadata_only=1` at the database layer.
- **Store adapter** — `ConstructionStore` gains upsert/get/list helpers for each table plus
  idempotent `add_email_message_recipient` and `enqueue_email_review_item` (INSERT OR IGNORE on
  their UNIQUE keys), `list/count_email_review_queue`, and crawl-run + processing receipts. Every
  mutating helper raises `ValueError` on a no-mutation / no-full-body / no-attachment-content flag
  before any SQL runs.
- **Evidence** — `docs/evidence/construction-intelligence-phase-06-email/`
  `03-email-schema-and-migrations.md` + captured `email-schema-validation.txt`.

## Prompt 04 — read-only mail client + endpoint guard + `graph mail status`

Makes the mail read path operational while keeping the mailbox read-only at the HTTP layer.

- **Endpoint guard** — `graph/mail_endpoint_guard.py` (`MailboxMutationBlockedError`,
  `load_mail_endpoint_contract`, `assert_mail_request_allowed`). Loads the Prompt 01 repo YAML
  contract and refuses any request that is not an allowlisted GET, *before* the HTTP call.
  Positive-allowlist-first so legitimate folder reads (even by well-known name) never false-positive
  on a mutation keyword; forbidden literals live only in the YAML, so `graph/` source stays clean for
  the `test_mutation_lockout` static scan.
- **Read-only client** — `graph/mail_readonly_client.py` (`ReadOnlyMailClient`): guarded GET wrappers
  over `GraphHttpClient` for identity, folders, message metadata, and attachment metadata. Uses the
  contract's metadata-only `$select` (full `body` and attachment `contentBytes` excluded); exposes no
  mutation method.
- **CLI** — new top-level `graph` group (`cli/graph.py`, registered in `cli/main.py`) with `graph mail
  status [--json] [--probe/--no-probe]`: reports redacted auth/scope readiness, runs an in-process
  guard self-test (every allowlisted GET allowed, every forbidden verb/path blocked), and issues one
  bounded `/me/mailFolders` probe through the guarded client.
- **Evidence** — `docs/evidence/construction-intelligence-phase-06-email/`
  `04-readonly-graph-client-and-auth-status.md` + captured `graph-mail-auth-status.json` (live: guard
  self-test passed, probe 200, all guardrails true, no token leaked).

### Five-layer read-only lock (defense in depth)

1. **Model** — Pydantic `Literal` (raises `ValidationError`).
2. **Adapter** — `ValueError` before SQL.
3. **Database** — SQLite `CHECK` (raises `IntegrityError`).
4. **Scope** — runtime requests `Mail.Read` only.
5. **HTTP endpoint guard** — `assert_mail_request_allowed` raises `MailboxMutationBlockedError`
   before any mail HTTP request that is not an allowlisted GET (Prompt 04).

Naming reconciliation: new operational email tables use the package's `email_*` family (Prompt 03
extends it); the active policy lives beside the deferred one in `construction/policy/` rather than a
new `email_intelligence/` package (which may emerge as later modules land). Evidence:
`docs/evidence/construction-intelligence-phase-06-email/` (`00`/`01`/`02` numbered docs,
`mail-permission-readiness-proof.md`, `mailbox-source-registry-proof.md`,
`mailbox-readonly-guardrail-proof.md`, and the endpoint-contract research doc).
