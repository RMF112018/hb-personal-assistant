# 17 — Operational Email Intelligence (Phase 06)

Status: **in progress** · Phase 06 Prompts 00–09 landed · Migration **V12** · read-only mail client + endpoint guard (Prompt 04) · folder discovery + sync state (Prompt 05) · message metadata indexing (Prompt 06) · project-aware discovery (Prompt 07) · attachment metadata + source-link candidates (Prompt 08) · encrypted full-body storage (Prompt 08A) · relationship candidates (Prompt 09)

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

## Prompt 08 — attachment metadata + source-link candidates

Enriches attachment handling during `index` (no separate command), metadata-only, never content.

- **Analyzer** — `construction/email/attachment_analyzer.py`: pure `analyze_attachment(name,
  content_type, is_inline)` classifies link (`.url`/sharepoint/onedrive name), document /
  source-link-candidate (non-inline document type), and sensitivity (filename → one of the 20
  `email_sensitivity_review_categories.json` categories → level + `review_required`), with a redacted
  `[redacted:hash].ext` name. `detect_drive_links(bodyPreview)` finds a SharePoint/OneDrive host.
- **Indexer integration** — `_index_attachments` enriches each attachment row (`name_redacted`,
  `sharepoint_or_onedrive_link_detected`, `sensitivity_hint`, `review_required`), creates a
  `*_drive_item` source-link `email_relationship_candidates` row per document + a body-preview link
  candidate per message, and enqueues `email_review_queue` rows for sensitive attachments. New counters
  surface in the `index` JSON; candidate/review counts recorded on the crawl run. Idempotent.
- **No content** — `content_downloaded=0` / `metadata_only=1` for every row; analyzer reads
  name/content-type only; `$value` never called. Filenames/URLs stored as hashes only.
- **Evidence** — `08-source-link-and-relationship-candidate-proof.md` (live: 94 attachments, 5
  sensitive, 22 source-link candidates, 6 review items; 0/94 content downloaded).

## Prompt 08A — encrypted full email body storage (posture change)

Evolves the prior "no full body persistence" posture to "full body persistence allowed **only when
encrypted at rest**". This stays consistent with the repo's non-negotiables: plaintext is never logged,
committed, or stored in SQLite/Obsidian/evidence — it lives encrypted outside the repo via the existing
`security/text_vault` (Fernet). The mailbox remains strictly read-only.

- **Policy** — `email_active.py` + YAML add `full_body_storage_allowed` (true), `full_body_storage_mode`
  (Literal `encrypted_text_vault`), and hard-locked falses for plaintext/Obsidian/evidence/log body
  persistence + attachment-content storage + mailbox mutation, plus `max_full_body_fetch_per_run`
  (bounded 1–1000). The V10 policy table/adapter are unchanged (model fields are decoupled).
- **Schema** — Migration **V12** side table `email_message_body_vault_refs` (PK `message_id`): stores
  `encrypted_full_body_ref` + hash/length/content-type/review/sensitivity, with
  `CHECK(plaintext_persisted=0)` and obsidian/evidence/log body-persistence CHECKs. No plaintext column;
  `email_messages.full_body_persisted=0` preserved.
- **Read path** — `body_fetch_select` contract key + `ReadOnlyMailClient.get_message_body` (guarded
  `GET /me/messages/{id}` with body `$select`). The default metadata path stays body-free.
- **Capture** — `EmailMessageIndexer.index(include_encrypted_body=True)` (policy-gated, bounded by the
  per-run budget) fetches each body, `hashlib.sha256` + length, classifies sensitivity in-memory
  (`classify_text_sensitivity` → review), `text_vault.encrypt_text`, persists the ref, and **discards the
  plaintext**. CLI `graph mail index --include-encrypted-body`; dry-run reports eligibility only.
- **Controlled read** — `graph mail body show --message-id --reason [--show-plaintext] --json` is
  **local-only** (vault + DB, no Graph): default redacted summary, `--show-plaintext` to terminal only,
  every read writes a `body_decrypt_read` audit receipt (no plaintext).
- **Deferred to later prompts** — review-routing/summaries/Obsidian *consumption* of the encrypted body
  is deferred (those email commands don't exist yet); the policy locks (`obsidian_full_body_allowed=False`)
  pre-constrain them, and sensitive captured bodies already set `review_required` on the vault ref.
- **Evidence** — `10A-*` (preflight, policy proof, schema proof, indexing dry-run JSON, encryption proof,
  decrypt proof, no-leak proof, no-mutation proof). Live: 5 real bodies encrypted (0/5 plaintext).

## Prompt 09 — relationship candidates (local synthesis)

Synthesizes the cross-system candidate graph, **local-only** (no Graph/mailbox), from stored email
intelligence + the repo's Procore/calendar/drive tables.

- **Builder** — `construction/email/relationship_builder.py` (`RelationshipCandidateBuilder`,
  `RelationshipReport`, `RelationshipCandidate`). Per project-matched message (from `email_project_matches`,
  within lookback): emits a `project` candidate, a `procore_*` candidate when the sender is a Procore
  notification (control type from the bounded preview), a `procore_payment_application|invoice|contract`
  candidate when a financial keyword appears **and** financials are available (→ review), and a
  `calendar_event` candidate on Outlook meeting-email patterns. Counts existing Prompt 08 `*_drive_item`
  file candidates; surfaces Procore/drive/calendar availability counts.
- **Not determinations** — every candidate carries confidence + `review_required` + a redacted "possible
  …" evidence string; financial/legal-sensitive topics route to review. The report disclaims
  determinations. Repo helpers `list_email_project_matches` / `list_email_relationship_candidates` added.
- **CLI** — `graph mail relationships --project … --lookback-days … [--dry-run/--no-dry-run] --json`
  (default persist). Idempotent (deterministic `candidate_id`).
- **Evidence** — `09-relationship-candidates-proof.md` + `email-relationship-candidates.json` (live: 40
  matched messages → 47 candidates incl. 7 Procore; Procore availability rfis 72 / submittals 100 /
  meetings 96 / financials 74).

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

## Prompt 10 — Review routing, sensitive categories & encrypted-body eligibility (schema V13)

Adds the review-routing / eligibility layer over the already-indexed, project-matched
email. **Local-only** (no Graph, no mailbox): reads persisted `email_project_matches` +
`email_messages` (bounded, redacted previews) and decides, per message, (1) which
sensitive categories apply, (2) whether the message is eligible for a read-only full-body
fetch and encrypted-at-rest storage, and (3) whether it must be routed to review before
any body-derived intelligence is trusted.

- **`construction/email/review_categories.py`** — authoritative 23-category registry
  (`ReviewCategory` + `REVIEW_CATEGORIES` + `classify_review_categories`). Reproduces the
  19 legacy `attachment_analyzer` categories exactly and adds
  `confidential_bid_or_estimate`, `owner_directive`, `subcontractor_default`,
  `schedule_recovery_or_acceleration`. Mirrored to
  `resources/config/email_sensitivity_review_categories.json` (drift-guarded by test).
- **`construction/email/review_router.py`** — `ReviewRouter` + `EmailBodyCaptureDecision`.
  Eligibility is policy-gated (`full_body_storage_allowed`, mode `encrypted_text_vault`),
  folder-scoped (excludes deleted/junk/drafts), per-run capped
  (`max_full_body_fetch_per_run`), and lookback-bounded. Sensitive / low-confidence
  (`< low_confidence_threshold` 0.75) messages route to `email_review_queue`. Plaintext
  body persistence is never represented as allowed.
- **Migration V13** (`v13_email_review_body_capture_decision`) — additive
  `ALTER TABLE email_review_queue ADD COLUMN` × 4: `body_capture_eligible`,
  `encrypted_body_capture_allowed`, `review_required_before_body_use`,
  `body_capture_decision_json`. ADD COLUMN only (gated behind the version row so re-apply
  is safe); no plaintext-body column.
- **CLI** — `graph mail review-queue --project … [--lookback-days N] [--max-messages N]
  [--dry-run/--no-dry-run] --json` (local-only; default dry-run preview, evidence-safe).

Guardrails unchanged: read-only mailbox, no mutation path, no full-body plaintext in
SQLite/Obsidian/evidence/logs/CLI JSON. Evidence:
`docs/evidence/construction-intelligence-phase-06-email/10-review-routing-and-encrypted-body-eligibility.md`
+ `email-review-routing-proof.md` + `email-review-routing-dry-run.json`.
