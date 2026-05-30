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
