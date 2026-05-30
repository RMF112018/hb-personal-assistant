# 01 — Official Microsoft Graph Files Research & Endpoint Contract

**Prompt:** Prompt 01 — Official Graph Files Research and Endpoint Contract
**Phase:** HB Construction Intelligence Phase 06 — SharePoint / OneDrive File Intelligence
**Date:** 2026-05-30
**Posture:** Documentation + static contract resources only. No runtime code, schema, scope, or
CLI changes. (Required work item 4: "Do not implement code changes unless needed for resource files.")

This record establishes the authoritative read-only Microsoft Graph **files** endpoint contract for
the phase. The Prompt 02 runtime guard will enforce it; Prompts 03+ build the workflows on top of it.

---

## 1. Official Graph References

Endpoint behavior below is grounded in the official Microsoft Graph v1.0 documentation:

- Get drive — https://learn.microsoft.com/en-us/graph/api/drive-get?view=graph-rest-1.0
- List drives — https://learn.microsoft.com/en-us/graph/api/drive-list?view=graph-rest-1.0
- Get site — https://learn.microsoft.com/en-us/graph/api/site-get?view=graph-rest-1.0
- driveItem resource — https://learn.microsoft.com/en-us/graph/api/resources/driveitem?view=graph-rest-1.0
- List children — https://learn.microsoft.com/en-us/graph/api/driveitem-list-children?view=graph-rest-1.0
- Download content — https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0
- Delta — https://learn.microsoft.com/en-us/graph/api/driveitem-delta?view=graph-rest-1.0
- Paging — https://learn.microsoft.com/en-us/graph/paging
- Throttling — https://learn.microsoft.com/en-us/graph/throttling

---

## 2. Read Operations In Scope (GET only)

Recorded authoritatively in `resources/config/graph_files_read_endpoint_allowlist.yaml`
(`version: 1`, `permission_tightening: deferred`). Each entry is tagged `repo_confirmed` (already
called by existing code) or `forward_looking` (sanctioned for later prompts).

| Endpoint | Provenance | Repo caller |
| --- | --- | --- |
| `GET /me/drive` | repo_confirmed | `construction/graph/resolver.py:447` |
| `GET /me/drives` | forward_looking | — |
| `GET /users/{userId}/drive` · `/users/{userId}/drives` | forward_looking | — |
| `GET /sites/{hostname}:/{server-relative-path}` | repo_confirmed | `resolver.py:212,272,335` |
| `GET /sites/{siteId}` | forward_looking | — |
| `GET /sites/{siteId}/drive` | repo_confirmed | `resolver.py:222,282` |
| `GET /sites/{siteId}/drives` | repo_confirmed | `resolver.py:409` |
| `GET /sites/{siteId}/pages` | repo_confirmed | `resolver.py:384` (linked-library discovery) |
| `GET /drives/{driveId}` · `/root` · `/root/children` | forward_looking | — |
| `GET /drives/{driveId}/root:/{itemPath}` | repo_confirmed | `resolver.py:294` (folder by path) |
| `GET /drives/{driveId}/items/{itemId}` · `/children` | forward_looking | (OneDrive `/me/drive/items/{id}` confirmed) |
| `GET /me/drive/items/{itemId}` · `/children` | repo_confirmed | `graph/drive_item_client.py:24,40` |
| `GET /drives/{driveId}/root/delta` | repo_confirmed | `construction/graph/delta_crawler.py:108,118,124,136,218` |
| `GET /drives/{driveId}/items/{itemId}/delta` | repo_confirmed | `delta_crawler.py:101` (folder-scoped) |
| `GET /me/drive/root/delta` | repo_confirmed | `delta_crawler.py:129,132` |
| `GET /drives/{driveId}/items/{itemId}/content` | forward_looking | (controlled, flag-gated) |
| `GET /me/drive/items/{itemId}/content` | repo_confirmed | `drive_item_client.py:86` (controlled, flag-gated) |

**Reconciliation note — endpoints added beyond the package draft.** The package draft allowlist
(`resources/json/graph_files_read_endpoint_allowlist.json`) omitted endpoints that existing repo
code already calls. The repo-truth allowlist therefore **adds**: `/sites/{siteId}/pages`,
`/me/drive/root/delta`, `/drives/{driveId}/root:/{itemPath}`, `/drives/{driveId}/root` and
`/root/children`, and the OneDrive `/me/drive/items/{itemId}` family. Source code is authoritative
over the planning package.

Microsoft Graph file **search** APIs are treated as optional/supplemental only and must never
replace source-of-truth inventory + delta indexing.

---

## 3. Mutating Operations Out of Scope (hard "no writeback" boundary)

Recorded authoritatively in `resources/config/graph_files_mutation_endpoint_blocklist.yaml`
(`version: 1`). Forbidden verbs: `POST, PUT, PATCH, DELETE`. Forbidden operations (path + keyword):
upload / replace content, create child/folder, update metadata, delete/restore, copy, move, create
sharing link, invite/permission change, `permissions`, `createUploadSession`, checkout / checkin /
discardCheckout, retention label, sensitivity label.

This boundary holds **even though the tenant has consented broad write-capable scopes**
(`Files.ReadWrite.All`, `Sites.ReadWrite.All`, `Sites.Manage.All`, `Sites.FullControl.All` — see
§7). Behavioral read-only is enforced independently of granted scopes.

**Existing static guarantee.** `tests/test_mutation_lockout.py`
(`test_no_m365_write_apis_in_graph_clients`, `test_graph_clients_do_not_contain_mailbox_mutation_endpoints`)
statically scans `src/hb_assistant/graph/**.py` for write verbs / mutation endpoints. The contract
therefore lives in `resources/config/` data files, **not** as literal strings inside `graph/*.py`
modules — identical to the rationale in `graph/mail_endpoint_guard.py`.

---

## 4. Delta Requirements

The delta workflow (recorded under `delta:` in the allowlist YAML) must:

1. Start without a token for initial enumeration.
2. Follow `@odata.nextLink` until exhausted (apply the whole URL verbatim; never parse/manipulate
   `$skiptoken`).
3. Store `@odata.deltaLink` for future change checks.
4. Use the previously stored delta link for the next sync.
5. Handle deleted items via the `deleted` facet (mark them; never delete in the source system).
6. Detect stale tokens / **`410 Gone` (resyncRequired) → structured `requires_rebaseline` state**.
7. **Never render raw delta links** in Markdown, logs, or evidence — only a fingerprint.

This matches the existing `ConstructionDeltaCrawler` behavior (token persistence + receipts) and
extends it with the explicit `410 → requires_rebaseline` rule for hardening in Prompt 08.

---

## 5. driveItem Metadata Requirements

Recorded authoritatively in `resources/config/graph_files_drive_item_metadata_field_contract.yaml`
(`version: 1`).

- **Required identity:** `source_id`, `drive_id`, `drive_item_id`.
- **Preferred metadata (when present):** `name`, `webUrl`, `size`, `createdDateTime`,
  `lastModifiedDateTime`, `eTag`, `cTag`, `parentReference`, `sharepointIds`, `file`, `folder`,
  `package`, `remoteItem`, `deleted`, and `quickXorHash` where returned.
- **Never persist / cache:** **`@microsoft.graph.downloadUrl`** (short-lived signed URL — re-resolve
  per download, never store), `Authorization`, `access_token`, `refresh_token`, `id_token`, and the
  raw `@odata.deltaLink` / `@odata.nextLink` (fingerprint only).

The `$select` set in the read allowlist (`drive_item_metadata_select`) is content-free by
construction, keeping enumeration metadata-only.

---

## 6. Throttling Requirements

Recorded under `throttling:` in the allowlist YAML and already implemented by the shared client:

- Handle HTTP `429`; honor `Retry-After`.
- Back off on transient `5xx` (`500/502/503/504`).
- Prefer delta after baseline; avoid repeated full crawls.
- Record retry counts and **redacted** errors in sync receipts.

**Repo reuse.** `graph/http_client.py` `GraphHttpClient` already provides the enforcement
primitives: `RETRY_STATUSES = {429, 500, 502, 503, 504}`, exponential backoff
(`MAX_RETRIES`/`BASE_BACKOFF`/`MAX_BACKOFF`), `get_all_pages()` with `max_pages`/`max_items`
guards, sanitized `GraphHttpError` (no Authorization/body/token leakage), and bounded
`download_to_file()` streaming with a `max_bytes` ceiling. The files phase builds on this client
rather than introducing a new HTTP path.

---

## 7. Deferred Permission Posture (carried forward, NOT changed)

Permission tightening remains **deferred** for the entire phase. No configured scope was removed or
narrowed by this prompt. Runtime config still requests `Files.ReadWrite.All`
(`config/models.py` `IdentityConfig.delegated_scopes`) and the resolver requests
`["Sites.Read.All", "Files.ReadWrite.All", "User.Read"]`; the active cached token additionally
carries `Sites.ReadWrite.All`, `Sites.Manage.All`, `Sites.FullControl.All`, `AllSites.FullControl`
(see `00-repo-truth-baseline.md` §4). The allowlist/blocklist contract here constrains **behavior**
to read-only regardless of those grants. Standing remediation record is deferred to
`22-deferred-permission-tightening-record.md`.

---

## 8. Reconciliation Summary (package vs. repo truth)

| Package instruction | Decision in this prompt |
| --- | --- |
| "Create endpoint allowlist/blocklist **JSON** resources" under `resources/json/` | Authored as **YAML under `resources/config/`** to mirror the established mail-guard precedent (`graph_mail_*_endpoint_*.yaml`) so the Prompt 02 files guard reuses the same `yaml.safe_load` + `PathPolicy().resolve_repo_root()` loader. Content is equivalent to the package's draft JSON. |
| Package draft allowlist endpoint set | Extended with repo-confirmed endpoints actually called by resolver/crawler/client (§2). |
| `drive_item_metadata_field_contract` | Authored as YAML; `never_persist` expanded to include `id_token` and raw `@odata.deltaLink`/`@odata.nextLink`. |
| Runtime guard / CLI / schema | **Out of scope** for Prompt 01; deferred to Prompt 02 (guard) and Prompt 03+ (CLI). |

---

## 9. Artifacts Produced

- `resources/config/graph_files_read_endpoint_allowlist.yaml`
- `resources/config/graph_files_mutation_endpoint_blocklist.yaml`
- `resources/config/graph_files_drive_item_metadata_field_contract.yaml`
- `docs/evidence/construction-intelligence-sharepoint-onedrive/01-official-graph-files-research.md` (this file)

---

## 10. Stop-Condition Check

No stop condition triggered. This prompt introduced **no** Microsoft 365 writeback, required **no**
permission tightening, copied **no** source files into Obsidian, persisted **no** full source
document text, exposed **no** raw delta links, and bypassed **no** sensitive-file review routing.
The over-broad-permission risk is documented and **deferred**. No tokens, Authorization headers,
signed URLs, raw delta links, full bodies, PEMs, or secrets appear in any artifact.
