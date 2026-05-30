# 17 — Operational Email Intelligence (Phase 06)

Status: **in progress** · Phase 06 Prompts 00–07 landed · Migration **V11** (Prompt 03) · read-only mail client + endpoint guard (Prompt 04) · folder discovery + sync state (Prompt 05) · message metadata indexing (Prompt 06) · project-aware discovery (Prompt 07)

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

## Prompt 05 — folder discovery + sync state

Resolves the policy-driven mailbox registry against the live mailbox and initializes per-folder sync
state, all read-only.

- **Service** — `construction/email/folder_discovery.py` (`EmailFolderDiscovery`,
  `FolderDiscoveryResult`, `DiscoveredFolder`), the first module in the new `construction/email/`
  package (higher layer: imports the `graph/` read client + the `construction/store` helpers).
  **List-then-match**: one `get_me` + one `list_mail_folders` GET, the Prompt 02 registry
  (`build_mailbox_source_registry`) resolved to live folders by display name. Unmatched policy folders
  (e.g. a mailbox with no Archive) are reported, not persisted.
- **Persistence** — for each matched folder `upsert_email_source_location` (resolved `folder_id`, owner
  sha256[:16] hash, `include_in_sync` per policy); for each **included** matched folder
  `upsert_email_sync_state` (`bounded_lookback`, `default_lookback_days`, `pending`). Excluded folders
  (Deleted Items / Junk Email / Drafts) are recorded with `include_in_sync=0` and **no** sync cursor.
- **CLI** — `graph mail folders [--json] [--dry-run/--no-dry-run]` (default dry-run previews; `--no-dry-run`
  commits). JSON surfaces owner hash, per-folder roles/counts, and `folder_id_fingerprint`s (never raw
  ids/tokens).
- **Evidence** — `05-folder-discovery-dry-run.md` (live: all 6 policy folders resolved against Bobby's
  mailbox; 6 source rows + 3 included sync cursors persisted; excluded folders carry no cursor).

## Prompt 06 — message metadata indexing

Bounded, read-only indexing of message metadata into local SQLite (the corpus later prompts match,
relate, and summarize).

- **Service** — `construction/email/message_indexer.py` (`EmailMessageIndexer`, `IndexResult`,
  `IndexedFolder`). Reads included folders' raw `folder_id` from `email_source_locations`, then per
  folder lists bounded messages (`received_after` `$filter` + `$top` + `max_items` cap), normalizes
  each to a **redacted, metadata-only** record (`redact_subject`/`hash_value`/`truncate_preview`;
  `thread_key = conversation_id or hash(internet_message_id | normalized-subject + participant
  domains)`), and upserts `email_messages` + `email_message_recipients` (`is_bobby` flagged by owner
  hash) + `email_message_attachments` (metadata-only). Records one `email_crawl_runs` row per folder +
  one `email_processing_receipts` row per run.
- **Idempotent** — message/recipient/attachment rows upsert by stable keys (re-run = stable counts);
  crawl-run + receipt rows are append-only audit logs. Proven live: 52 messages / 237 recipients / 73
  attachments stable across two runs.
- **CLI** — `graph mail index --project … --lookback-days … --max-messages … [--dry-run/--no-dry-run]
  --json` (default persist). `--project` is a validated crawl-run **label**; project *matching* is a
  later prompt.
- **Contract fix** — removed `sensitivity` from the Prompt 01 `message_metadata_select` (not a valid
  Graph v1.0 `message` property; HTTP 400 on live select).
- **Evidence** — `06-message-metadata-index.md` (live counts + idempotency proof).

## Prompt 07 — project-aware discovery

Matches the bounded message window to pilot projects, read-only, with subject matched in-memory.

- **Matcher** — `construction/email/project_matcher.py`: pure `ProjectMatcher` scoring a message's
  in-memory metadata against a `ProjectDescriptor` via weighted signals (`PROJECT_MATCH_SIGNALS`): HB
  number in subject (1.00) / preview (0.95), SharePoint-OneDrive link (0.90), Procore notification
  (0.85), name in subject (0.80) / preview (0.70), known domain (0.60, inert until configured), thread
  continuation (0.75). Descriptors are built from the **seed registries** (`load_procore_projects` pilot
  set + `load_source_registry` HB number/normalized name) — the DB `construction_project_identity` is
  unseeded.
- **Discovery** — `construction/email/project_discovery.py` (`ProjectEmailDiscovery`): reads the bounded
  window live, matches each message × descriptor, runs a thread-continuation pass, and produces a
  metadata-only `DiscoveryReport` (counts + signal histograms). `--no-dry-run` persists
  `email_project_matches` (one row per signal) + the message verdict (`project_number_detected`,
  `project_match_confidence`, `review_required`); the message is upserted first so the FK holds.
- **CLI** — `graph mail discover --project … --lookback-days … [--dry-run/--no-dry-run] --json` (default
  dry-run). Subject/bodyPreview matched in-memory, never persisted raw.
- **Shared normalization** — `normalize_message` / `compute_thread_key` promoted from the indexer for
  reuse by the discovery persist path.
- **Evidence** — `07-project-aware-discovery.md` + `email-discovery-dry-run.json` (live: 202 scanned, 40
  matched to tropical) + `email-project-match-test-results.json` (8/8 matcher fixtures pass).

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
