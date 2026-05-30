# 18 — SharePoint / OneDrive File Intelligence (Phase 06, Files)

**Status:** IN PROGRESS (phase opened 2026-05-30). This record grows across the phase; it currently
documents the components delivered through Prompt 02. Authoritative per-prompt evidence lives under
`docs/evidence/construction-intelligence-sharepoint-onedrive/`.

> Sibling phase: `17-email-intelligence-phase-06.md` (the Phase 06 *email* track). This is the
> separate Phase 06 *SharePoint/OneDrive file* track.

## Goal

Pull delegated Microsoft Graph SharePoint / OneDrive file **metadata** (and, under controlled
flag-gated extraction, bounded redacted excerpts) into the local SQLite store and source-linked
Obsidian projections — behaviorally read-only, project-aware, with sensitive files routed to review.

## Critical deferred scope

Permission tightening is **deferred for the entire phase** (user instruction; `12_DECISION_REGISTER`).
The tenant consents broad write-capable scopes (`Files.ReadWrite.All`, `Sites.ReadWrite.All`,
`Sites.Manage.All`, `Sites.FullControl.All`, `AllSites.FullControl`) and runtime config requests
`Files.ReadWrite.All`. These are **documented, not narrowed**. The standing record is
`docs/evidence/construction-intelligence-sharepoint-onedrive/22-deferred-permission-tightening-record.md`.

## Components delivered (through Prompt 02)

### Endpoint contract (Prompt 01) — `resources/config/`
- `graph_files_read_endpoint_allowlist.yaml` — GET-only; allowed drive/site/driveItem/delta/content
  read patterns (reconciled to what the resolver/crawler/client actually call); paging + throttling
  + delta discipline (tokenless start → store `@odata.deltaLink`; `deleted` facet;
  `410 → requires_rebaseline`; never render raw delta links).
- `graph_files_mutation_endpoint_blocklist.yaml` — forbidden verbs (`POST/PUT/PATCH/DELETE`) +
  upload/share/move/copy/permission/checkout/label paths & keywords.
- `graph_files_drive_item_metadata_field_contract.yaml` — required identity, preferred metadata,
  and `never_persist` (`@microsoft.graph.downloadUrl`, tokens, raw delta/next links).

### Read-only endpoint guard (Prompt 02) — `src/hb_assistant/graph/files_endpoint_guard.py`
Mirrors `mail_endpoint_guard.py`. `FilesEndpointContract` + `load_files_endpoint_contract()` load the
three YAMLs; `assert_files_request_allowed(method, path)` is positive-allowlist-first and raises
`FileMutationBlockedError` before HTTP on any non-GET / mutation path / forbidden keyword.
`run_files_no_writeback_self_test()` provides a deterministic, network-free proof. The module holds
**no literal mutation-endpoint strings** (loaded from YAML) so the `test_mutation_lockout` static
scan of `graph/**.py` stays clean. *Not yet wired into a live read client — that lands with the
discovery client (Prompt 04).*

### No-writeback proof command (Prompt 02) — `hb-assistant graph files no-writeback-proof --json`
New `graph files` Typer subgroup (sibling of `graph mail`) in `cli/graph.py`. Offline/deterministic;
combines the guard self-test, a source static scan of `graph/` + `construction/graph/` + `files/`
(zero mutating verb calls), a contract summary, and a redacted permission-posture section
(scope NAMES only). Emits `permission_tightening: "deferred"`.

### Canonical source-registry projection (Prompt 03) — `hb-assistant graph files sources [--apply]`
Makes the pre-existing V5 projection (`construction/source_projection.py` →
`project_registry_to_v5_source_locations`, backed by `ConstructionStore.upsert_source_location`)
**operator-reachable**. A `dry_run` mode was added so dry-run (the default) classifies/validates the
14 seed sources (enabled / pending / pre-resolved / matched-unmatched / review_required) and computes
the projection plan with **zero** SQLite writes; `--apply` persists idempotently into
`construction_source_locations` (re-apply keeps 14 rows, no duplicates). Read-only is enforced at
three layers (model `Literal[True]`, store `ValueError`, SQLite `CHECK(read_only=1)`); invalid
read_only / vault-copy / full-text / deep-index-of-review-required policy is rejected. No new
migration — the V5 table already supports this; the package's proposed ingestion/download/extraction
tables are deferred to later prompts. The resolver/crawler still write the V2 inventory shape;
migrating those to V5 is later work.

### SharePoint site & drive discovery (Prompt 04) — `graph files sites` / `site resolve` / `drives`
`construction/graph/site_drive_discovery.py` (`SiteDriveDiscovery`) reuses `ConstructionGraphResolver`
for site resolution (URL + pre-seeded ID + ProjectHome `sharepoint_site_page` linked-source
candidates, `deep_index_allowed=False`) and adds drive **enumeration + matching**: it guard-asserts +
reads `GET /sites/{site_id}/drives` (metadata `$select` only — no `/items`/`/content`) and matches a
configured source by precedence `drive_id`(high) → `list_id`(high) → `library_name`(medium) →
`webUrl`(medium); no match → `unmatched` (no silent default-drive fallback). Three CLI commands
(dry-run default; `--apply` persists), with structured `auth_required` degradation when no delegated
token is cached. Discovery receipts reuse the generic `construction_processing_receipts` table
(`operation=site_discovery|drive_discovery`) — **no new migration**; the package's proposed typed
discovery tables are deferred. The enumeration GET is asserted through `assert_files_request_allowed`
(first live use of the Prompt 02 guard).

> Guard-wiring scope note (supersedes the Prompt 02 forward reference): full HTTP-layer guard
> interception of every files read — including the resolver's colon-addressed site-by-URL path
> (`/sites/{host}:/{path}`, which the guard's segment matcher cannot yet match) — plus the matcher
> enhancement, is deferred to the **controlled-download client (Prompt 11)**, where mutation risk is
> highest. The discovery path is read-only by construction (GET-only) and covered by the
> `test_mutation_lockout` static scan over `construction/graph/`.

### OneDrive discovery & shared-library posture (Prompt 05) — `graph files onedrive`
`SiteDriveDiscovery.discover_onedrive` extends the discovery service to OneDrive: business/personal
roots resolve via the resolver's `/me/drive` plus a guard-asserted `/me/drives` enumeration
(`available_drives`, drive_type), with a `404` mapped to **`unavailable`** (personal OneDrive not
provisioned). Shared libraries are represented with structured states — `pre_resolved` (configured
`drive_id`) or **`requires_share_url`** (no id; resolution is **not forced**, no share URL
fabricated), carrying the registry `resolution_status` (`pending_source_resolution`). Status taxonomy:
`pre_resolved | resolved | pending | unavailable | requires_share_url | unsupported | error`. The
`graph files onedrive` command (dry-run default; `--apply` persists an `onedrive_discovery`
`construction_processing_receipts` row — no new migration) degrades to `auth_required` without a
token. Limitations recorded in `docs/evidence/.../18-shared-library-resolution-limitations.md`.

### Rich driveItem metadata indexing (Prompt 06) — `graph files index` + schema V15
`construction/graph/drive_item_indexer.py` adds `normalize_drive_item` (pure: raw Graph driveItem →
canonical V5 kwargs, handling file/folder/package/remoteItem/deleted facets, parentReference,
sharepointIds, eTag/cTag, createdDateTime, file hashes) and `DriveItemIndexer` (bounded, guard-
asserted read-only enumeration of a drive's delta endpoint → normalize → upsert into
`construction_drive_items`). **`@microsoft.graph.downloadUrl` is never read or stored** (dropped from
the normalized payload; facet JSON is redacted to strip any url/token-bearing keys), proven by the
`download_url_persisted: false` flag + tests. Schema **V15** (additive `ALTER TABLE ADD COLUMN`,
version-gated like V13; max schema version 14 → 15) extends `construction_drive_items` with
`is_package`, `e_tag`, `c_tag`, `created_datetime`, `parent_reference_path`, `folder_child_count`,
`sharepoint_web_id`, `sharepoint_list_item_id`, `file_hashes_json`, `package_json_redacted`,
`remote_item_json_redacted`, `first_seen_utc`, `last_seen_utc` (+ a `(deleted)` index);
`upsert_drive_item` extended accordingly (`first_seen_utc` preserved on conflict, `last_seen_utc`
refreshed). The `graph files index` command is dry-run default (`--apply` persists + writes a
`drive_item_index` receipt), degrading to `auth_required` without a token. Delta-token persistence +
410 rebaseline remain P08.

### User-provided link → ID resolution (Phase 06A) — `graph files link resolve` + schema V16
`construction/graph/link_resolver.py` resolves a browser sharing link to canonical IDs via the
read-only Graph **Shares API**: `encode_sharing_url` (`u!` + unpadded base64url) → guard-asserted
`GET /shares/{encoded}/driveItem` → normalize `drive_item_id`/`drive_id`/`parent_*`/`site_id`/
`list_id`/`list_item_id` + `item_kind` (file/folder/package/root_candidate). **Resolution, never
redemption** — no `Prefer: redeemSharingLink` header is sent (the shared `GraphHttpClient.get` cannot
send custom headers). Fallbacks: `/me/drive` for an own-OneDrive-root link, and a source-registry
host/path + project-number match (works offline without a token). Malformed links fail before any
Graph call. The **raw tokenized URL is never returned or persisted** — only a redacted URL
(query/fragment dropped, token-like path bits masked), a SHA-256 URL fingerprint, and a share-token
fingerprint; schema **V16** adds `construction_graph_link_resolution` with
`CHECK(raw_tokenized_url_persisted = 0)` (max schema version 15 → 16). `/shares/{id}` +
`/shares/{id}/driveItem` added to the read allowlist. The `graph files link resolve` command is
dry-run default (`--apply` persists a redacted row), degrading to `auth_required` (but still running
offline fallbacks). Evidence: `05a-user-provided-link-resolution-proof.json`; research addendum §11
in `01-official-graph-files-research.md`.

### Baseline crawl workflow (Phase 06A) — `graph files crawl`
`construction/graph/baseline_crawler.py` (`BaselineCrawler`) runs a bounded, **metadata-only** first
enumeration: prefers **delta-initial** traversal (`/drives/{id}/items/{folder}/delta` → `/root/delta`
→ `/me/drive/root/delta`), with an opt-in `--children` **non-recursive** traversal
(`/drives/{id}/items/{folder}/children` or `/root/children`) for *targeted diagnostics only*. Bounded
by `max_pages` (5), `max_items` (500), and a `max_seconds` (300) wall-clock budget via a custom
page-level loop (so `pages_seen` is counted and each page path — incl. `@odata.nextLink` — is
guard-asserted); `truncated_by` records which bound stopped it. Counts split `items_in_scope`
(normalized, non-deleted) vs `items_out_of_scope_filtered` (deleted tombstones / id-less). Reuses the
P06 `normalize_drive_item` + `upsert_drive_item`. On `--apply` it persists a
`construction_source_crawl_runs` row (`delta_link_recorded = False` — **baseline stores no token**;
delta-token persistence + 410 rebaseline are P08) and a `baseline_crawl` processing receipt — **no new
migration** (the crawl-runs table is V5). Dry-run default; degrades to `auth_required` without a
token. Evidence: `08-baseline-crawl-proof.json`.

### Delta sync hardening (Phase 06A) — `graph files delta`
`construction/graph/delta_sync.py` (`DeltaSync`) is the hardened **incremental** sync into the V5
canonical layer (the V2 `ConstructionDeltaCrawler` is left unchanged as the parallel path). It reads
the prior `construction_source_sync_state.delta_link` and starts incrementally (`started_from=
stored_delta`) or from the initial delta endpoint (`initial`), follows `@odata.nextLink` to
exhaustion, captures the final `@odata.deltaLink`, and on `--apply` persists it to SQLite **only**
(plus `delta_link_fingerprint`, last_successful/attempted, last_change_count, sync_status) via
`upsert_source_sync_state`, + a crawl-run row + a `delta_sync` receipt; the deleted facet upserts
`deleted=True`. **Raw-link redaction is the headline guardrail**: the raw delta/next links (and the
stored prior deltaLink used as the request path) live in SQLite only — the report/CLI/evidence carry
only `sha256:<12>` fingerprints, and the report `endpoint` is the logical delta template, never the
token-bearing URL. A stale token / `410 Gone` → `requires_rebaseline` (token cleared, status recorded
— never silently discarded). Truncation (max_pages/max_items) preserves the prior token
(status=`partial`). No new migration (sync-state table is V5). Dry-run default; `auth_required`
degradation. Evidence: `09-delta-sync-readiness-proof.md`, `21-delta-token-redaction-proof.md`.

### Project-aware file matching (Phase 06A) — `graph files project-match` + schema V17
`construction/graph/file_project_matcher.py` (`FileProjectMatcher`) assigns each indexed
`construction_drive_items` file to a project with qualitative confidence (high|medium|low|none),
status (matched|low_confidence|unmatched), and reason codes — **pure SQLite + source registry, no
Graph calls / no token**. Signals: source-registry project binding (deterministic, high), exact HB
project number `NN-NNN-NN` in path/name (high; reuses `email/project_matcher.HB_PROJECT_NUMBER_RE`),
normalized project name in path/name (medium), literal Procore project id (medium). **False-positive
prevention:** exact number equality only; ambiguous multi-project signals → `low_confidence` (never
auto-picked); no signal → `unmatched` (never forced to the queried `--project`); a file carrying a
*different* project's number matches *that* project, not the target. Low-confidence + unmatched route
to review via the canonical `review_required`/`review_reason` drive-item fields (the
`construction_review_queue` sensitive routing is Prompt 12). Schema **V17** (additive ALTER ADD COLUMN,
version-gated; max 16 → 17) adds `project_key`, `match_confidence`, `match_status`, `review_required`,
`review_reason`, `match_signals_json` (+ indexes); `update_drive_item_project_match` /
`list_drive_item_project_matches` written without touching `list_drive_items`/`V5DriveItem`. The CLI
is dry-run default (`--apply` writes the match fields), offline (no `auth_required` path). Evidence:
`10-project-file-match-results.json`.

### Ingestion eligibility policy (Phase 06A) — `graph files ingestion-policy` + schema V18
`construction/policy/file_ingestion.py` (`FileIngestionPolicy` + `load_file_ingestion_policy`, seed at
`resources/config/file_ingestion_policy.seed.yaml`; guardrail booleans `Literal`-locked) +
`construction/graph/ingestion_eligibility.py` (`IngestionEligibilityEvaluator`) gate every indexed
file with a disposition **before** any download/extraction (P11) — **offline: SQLite + policy +
registry, no Graph, no content read**. Reuses the existing `ReviewPolicyEvaluator` +
`review_required_rules.seed.yaml` for sensitive detection, the per-source `FolderPolicies`, and the
V17 project match. Most-restrictive-wins precedence yields `blocked_unsupported_type` /
`review_required` (sensitive) / `blocked_too_large` / `low_confidence` / `manual_approval_required`
(large-file warning band) / `metadata_only` / `eligible`. **`extraction_allowed` = `download_allowed`
= (disposition == eligible)**; everything else False. Schema **V18** adds
`construction_file_ingestion_decisions` (additive CREATE TABLE; max 17 → 18) with
`CHECK(review_required = 0 OR extraction_allowed = 0)` — a review-required file can never carry
extraction at the DB layer. Large-file thresholds (warning 25 MiB / block 100 MiB) ensure large files
never auto-extract. Dry-run default. Evidence: `11-ingestion-policy-proof.md`,
`19-large-file-policy-proof.md`.

### Controlled download & bounded extraction (Phase 06A) — `graph files extract` + schema V19
`construction/graph/controlled_extraction.py` (`ControlledExtractor`) is the **only** place file
content is fetched. It gates strictly on the V18 ingestion decisions — only `extraction_allowed`
(eligible, non-review) items proceed; review-required/blocked/etc. are skipped (`blocked_*`), a
runtime re-check on top of the DB CHECK. Download/extract require explicit `--download`/`--extract`
flags and are off in dry-run (plan only). It guard-asserts + `GET /drives/{drive_id}/items/{item_id}/
content` (drive-aware), streams bounded (`--max-bytes`) to a cache **outside repo/vault**
(`PathPolicy.get_cache_dir`), hashes (sha256), parses via the files `ParserRouter` into a **bounded
redacted** excerpt (emails/phones/long tokens masked; ≤ a char cap), and **deletes the cache after
parse** unless `--retain-cache`. Schema **V19** adds `construction_graph_download_receipts`
(CHECK `raw_download_url_persisted = 0`, `source_file_copied_to_vault = 0`) +
`construction_file_extraction_runs` (CHECK `full_text_persisted = 0`) — full text, raw download URLs,
and vault copies are forbidden at the DB layer (max 18 → 19). `cache_path_redacted` stores the
basename only; `@microsoft.graph.downloadUrl` is never used or cached. Dry-run default;
`auth_required` degradation. Evidence: `12-controlled-download-and-extraction-proof.md`,
`20-cache-retention-proof.md`.

### Sensitive file review routing (Phase 06A) — `graph files review-queue` (no new schema)
`construction/graph/file_review_router.py` (`FileReviewRouter`) routes construction-sensitive
SharePoint/OneDrive driveItems into the existing `construction_review_queue` (V3) **before** any
extraction. It is the V5 `construction_drive_items` counterpart to the V2-inventory
`ReviewQueueRouter`, reusing the same deterministic `ReviewPolicyEvaluator` (driveItem `name` +
`parent_path` only — no content body) and the idempotent `enqueue_review_item` (`INSERT OR IGNORE` on
`(source_key, item_id, rule_id)` — re-running never duplicates). The shared rule seed
(`resources/config/review_required_rules.seed.yaml`) grows from 16 → 25 rules, extending coverage
beyond the protected six (contract/financial/legal/incident/injury/personnel) to **claim, notice,
insurance_bonding, medical, dispute, cost_impact, schedule_impact**; the Pydantic validator still
passes (protected six intact, rule_ids unique). Low-confidence / unmatched project matches (V17
`match_status`) route via a synthetic `low-confidence-project-match` rule. The router cross-checks
that every routed item's V18 decision keeps `extraction_allowed = false` and reports
`extraction_blocked_for_all_routed`; the no-extraction guarantee itself is enforced by the V18 CHECK
(`review_required = 0 OR extraction_allowed = 0`) + the Prompt 11 extractor gate. **No new migration**
(schema stays at version 19); offline (no Graph); dry-run default. Evidence:
`14-sensitive-file-review-routing-proof.md`.

### Obsidian source manifests & project file registers (Phase 06A) — `graph files obsidian` (no new schema)
`construction/graph/file_obsidian_projection.py` (`FileObsidianProjector`) projects the V5 files SQLite
state into **grouped, low-noise** marker-bounded Obsidian notes under
`Work/HB Personal Assistant/07_File_Intelligence/`: a per-source **Source Manifest** (scope/site/drive
ids, item counts, last sync, and a **SHA-256 delta-link fingerprint only**), a per-project **File
Register** (counts by match status + ingestion disposition and a ≤50-row metadata table), a per-project
**File Review Summary** (the sensitive files Prompt 12 routed into `construction_review_queue`), and a
per-run **File Processing Receipt** (crawl + download/extraction counts with no-full-text / no-vault-
copy / no-signed-URL / no-raw-delta attestations). It mirrors `EmailObsidianProjector` — its own grouped
`_FileArtifact` list, marker-bounded `_write_artifact` (`<!-- HB-FILES-<KIND>:START/END -->`, regex
DOTALL in-place replace, idempotent), dry-run-default `project()`, and a Pydantic `FileObsidianReport` —
and **reuses** `delta_link_fingerprint`. An **output fence** (`_assert_output_fence`, run at build time
so dry-run previews are validated) raises on any raw delta token / signed-URL param / Graph downloadUrl
/ auth material / PEM block / full-text marker; it never creates one note per file. Offline (SQLite; no
Graph), no writeback, **no new migration** (schema stays at version 19). The V2 `ManifestService`
(construction-agent/email track) is intentionally untouched (parallel path). Evidence:
`13-obsidian-source-manifest-preview.md`.

### Read-only enforcement layers (defense-in-depth, scope-independent)
Source policy (`SourceLocation.read_only`), SQLite `CHECK(read_only=1)`, the files endpoint guard,
the extended `test_mutation_lockout.py` + `test_graph_files_endpoint_{contract,guard}.py`, and
`AppConfig.security.microsoft_365_writeback_enabled == False`.

## Forthcoming (later prompts)
Canonical source-registry projection (P03); SharePoint site/drive + OneDrive discovery (P04–05);
rich driveItem indexing (P06); baseline crawl + delta hardening (P07–08); project-aware matching
(P09); ingestion eligibility + controlled bounded extraction + sensitive review routing (P10–12);
source manifests / project file registers (P13); source-linked retrieval (P14); operational CLI +
runbooks (P15); end-to-end pilot + no-writeback proof (P16); final closeout (P17). The guard wiring
into the live files read client is part of P04.

## Guardrails (non-negotiable, enforced in code/tests)
No M365 writeback; behaviorally read-only at four layers; dry-run default for any SQLite/cache/Obsidian
write; no source-file copy into Obsidian; no full source text in vault notes; no token / Authorization
/ signed URL / raw delta link / full body / PEM / secret persisted; `@microsoft.graph.downloadUrl`
never cached.
