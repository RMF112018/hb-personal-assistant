# Phase 02 — Prompt 05 — Hilltop ProjectHome and Linked Source Discovery

## 1. Summary

Extends `ConstructionGraphResolver._resolve_sharepoint_site_page` from "site-id only" (Prompt 03) to full **page identity + linked-library candidate discovery**, without ever fetching drive contents.

For the canonical `sp_hilltop_gardens_projecthome` source the resolver now:

1. Resolves `site_id` via `/sites/{hostname}:{path}` (unchanged).
2. Resolves `page_id` via `/sites/{site_id}/pages?$select=id,name,webUrl&$top=50`, matching the page on tolerant `webUrl` equality (case-insensitive, trailing-slash tolerant, URL-decoded).
3. Enumerates linked-library candidates via `/sites/{site_id}/drives?$select=id,name,webUrl,driveType` and surfaces each as a `LinkedSourceCandidate` Pydantic record with `discovery_method="site_drives_enumeration"`.

Hard guardrails baked into the type system:

- `LinkedSourceCandidate.deep_index_allowed: Literal[False]` makes the candidate type itself un-able to grant deep-index permission. Operator triage must explicitly opt in elsewhere.
- A dedicated unit test asserts the resolver's HTTP call set never touches `/drives/{id}/items`, `/drives/{id}/root/children`, or `/drives/{id}/root/delta`. Discovery is pure metadata enumeration.
- If `/sites/{site_id}/drives` errors, page resolution still succeeds; candidates degrade to an empty list with a `note="linked_source_discovery_failed: graph_{status}"`.

No CLI surface change — `graph sources resolve --json` automatically surfaces `linked_sources_discovered` via `ResolutionResult.model_dump()`. No SQLite schema change — linked-source candidates are in-memory only this prompt; persistence to a V5 surface is deferred. The delta crawler's `skipped_unsupported_scope` behavior for `sharepoint_site_page` (from Prompt 03) is preserved verbatim.

## 2. Repo HEAD — Before / After

| Marker | Value |
| --- | --- |
| Branch | `main` |
| HEAD before | `65b2c7c1bdf1620b812436f614c34efec87aa050` ("feat(construction-agent): add baseline comparison primitive and tropical receipt") |
| HEAD after  | (recorded after commit) |
| Working tree before | clean |

## 3. Files Changed

**Modified (2):**

- `src/hb_assistant/construction/graph/resolver.py` — +125/-10. New `LinkedSourceCandidate` Pydantic sub-model with `Literal[False]` deep-index guardrail. New module-level `_canonicalize_url` helper for tolerant page URL equality. `ResolutionResult` gains `linked_sources_discovered: list[LinkedSourceCandidate]` (default empty). `_resolve_sharepoint_site_page` expanded from site-id-only to site-id + page-id + drives enumeration. New private helpers `_resolve_site_page_id` and `_discover_linked_sources` with sanitized error degradation.
- `tests/test_construction_graph_resolver.py` — +221/-12. Migrated the old `test_resolve_site_page_resolves_site_id_only` (which asserted Prompt 03's deferred-note behavior) into `test_resolve_site_page_when_pages_endpoint_returns_no_match`. Added 6 new tests covering the resolved happy path, URL-equality tolerance, no-page_url skip path, the no-drive-item-fetch guardrail, sanitized discovery error degradation, and the `LinkedSourceCandidate.deep_index_allowed` type-level guard.

**Created (1):**

- `docs/evidence/construction-intelligence-phase-02/05-hilltop-projecthome-discovery.md` — this file.

**Deleted:** none. **Schema migrations applied:** none.

## 4. Governance Attestation

| Reference | Status |
| --- | --- |
| `CLAUDE.md` §5 — "Obsidian Vault Planning and Implementation Package Governance" | Honored. No payloads copied under `docs/plans/**`; package consulted as guidance only. |
| `.grok/skills/vault-package-governance/SKILL.md` | Honored. |
| Phase 01 evidence (`session-handoff.md`, `11-final-closeout-summary.md`) | Carried forward as authoritative context. |
| Phase 02 package files | Reviewed (Prompt_05 spec + Workstream D — Hilltop ProjectHome). |

## 5. Validation Commands and Outputs

All from `/Users/bobbyfetting/hb-personal-assistant` on 2026-05-27.

### 5.1 `python -m pytest tests/test_construction_*.py tests/test_procore_*.py`

```text
........................................................................ [ 22%]
........................................................................ [ 44%]
........................................................................ [ 66%]
........................................................................ [ 88%]
.....................................                                    [100%]
325 passed in 3.27s
```

319 prior + 6 net new = 325. Resolver test count went 20 → 26.

### 5.2 `ruff check src/hb_assistant/construction/ src/hb_assistant/procore/ src/hb_assistant/cli/construction.py src/hb_assistant/cli/procore.py`

```text
All checks passed!
```

### 5.3 `hb-assistant construction-agent validate --json`

`ok=True, 4/4 passed` (schema_version=5, 6 projects, 14 sources).

### 5.4 `hb-assistant construction-agent sources validate --json`

```json
{"project_count": 6, "source_count": 14, "resolved_count": 0, "pending_count": 9, "deprecated_count": 0, "ok": true, "blocking": false}
```

### 5.5 `hb-assistant construction-agent index status --json`

`schema_version: 5` (unchanged).

### 5.6 `hb-assistant construction-agent graph auth status --json`

`token_type=none` (non-interactive shell, MSAL cache empty).

### 5.7 `hb-assistant construction-agent graph sources resolve --json`

`status=auth_required, targets=14` — unchanged because we cannot exercise the new code paths without a live token.

### 5.8 `hb-assistant procore mapping validate --json`

`ok=False, exit=1` by design (hilltop still pending in the separate procore_projects seed).

## 6. Hilltop ProjectHome Discovery Walkthrough (Mocked)

With a live token + the canonical `sp_hilltop_gardens_projecthome` source, the resolver would issue exactly these three Graph requests:

```text
1. GET /sites/hedrickbrotherscom.sharepoint.com:/sites/HilltopGardens
   → {"id": "<site-id>", "webUrl": "...HilltopGardens"}

2. GET /sites/<site-id>/pages?$select=id,name,webUrl&$top=50
   → {"value": [
         {"id": "<page-projecthome-id>", "name": "ProjectHome.aspx",
          "webUrl": ".../HilltopGardens/SitePages/ProjectHome.aspx"},
         ...
      ]}

3. GET /sites/<site-id>/drives?$select=id,name,webUrl,driveType
   → {"value": [
         {"id": "<drv-docs>",      "name": "Documents", "driveType": "documentLibrary", ...},
         {"id": "<drv-rfis>",      "name": "RFIs",      "driveType": "documentLibrary", ...},
         {"id": "<drv-submittals>","name": "Submittals","driveType": "documentLibrary", ...}
      ]}
```

The resulting `ResolutionResult.model_dump()` would look like:

```json
{
  "source_key": "sp_hilltop_gardens_projecthome",
  "kind": "sharepoint_site_page",
  "scope": "sharepoint_site_page",
  "status": "resolved",
  "site_id": "<site-id>",
  "page_id": "<page-projecthome-id>",
  "web_url": ".../HilltopGardens",
  "linked_sources_discovered": [
    {
      "drive_id": "<drv-docs>",
      "drive_name": "Documents",
      "web_url": "...",
      "drive_type": "documentLibrary",
      "library_kind": "documentLibrary",
      "discovery_method": "site_drives_enumeration",
      "deep_index_allowed": false,
      "item_count_hint": null,
      "note": null
    },
    {"drive_id": "<drv-rfis>", "drive_name": "RFIs",  "discovery_method": "site_drives_enumeration", "deep_index_allowed": false, ...},
    {"drive_id": "<drv-submittals>", "drive_name": "Submittals", "discovery_method": "site_drives_enumeration", "deep_index_allowed": false, ...}
  ]
}
```

Operator triage then decides which candidates become their own `SourceLocation` records in a later prompt. The resolver itself NEVER calls `/drives/<drv-docs>/items` or any equivalent content endpoint — this is asserted by the `test_resolve_site_page_never_fetches_drive_contents` unit test.

## 7. Guardrail Attestation

- External systems remain read-only. Discovery is `/sites/{id}/drives` metadata enumeration only — no content fetched, no SharePoint writeback, no source-file mutation.
- No deep indexing of linked libraries. `LinkedSourceCandidate.deep_index_allowed: Literal[False]` is enforced by Pydantic at construction time and verified by `test_linked_source_candidate_cannot_grant_deep_index_at_type_level`. The "no drive-content fetches" invariant is verified by `test_resolve_site_page_never_fetches_drive_contents`.
- No source-document copies into Obsidian (no rendering surface added).
- No full-document text in vault notes.
- No mailbox mutation paths.
- No live Graph round-trip exercised — non-interactive shell continues to emit structured `auth_required`. All tests use `MagicMock(spec=GraphHttpClient)`.
- Delta crawler unchanged for `sharepoint_site_page`: continues to emit `skipped_unsupported_scope` (no delta primitive for a page).
- Resolver gracefully degrades on partial failure: a Graph 503 from `/sites/{site_id}/drives` produces `linked_sources_discovered=[]` with a sanitized note, while page resolution still succeeds independently. The Phase 01 `GraphHttpError`-redaction path is unchanged.

## 8. Blocked Live / External Validation

- **Live Hilltop ProjectHome resolution** — requires interactive MSAL login. Code paths are exercised exclusively via mocked HTTP. Once a token is cached, `hb-assistant construction-agent graph sources resolve --source sp_hilltop_gardens_projecthome --apply --json` will populate `site_id`, `page_id`, and `linked_sources_discovered` from the real tenant.
- **Procore** — unchanged this prompt; OAuth still stubbed.
- **Webpart-level reference parsing** — `discovery_method="page_webpart_reference"` is reserved in the literal but not yet emitted by any code path; that surface lands in a later prompt.

## 9. Phase 02 Acceptance Progress

- **Hilltop ProjectHome site-id resolution** — closed (Prompt 03).
- **Hilltop ProjectHome page-id resolution** — closed (this prompt).
- **Linked-library candidate discovery** — closed (this prompt).
- **Deep-index opt-in workflow** — explicitly NOT introduced (guardrail).
- **Persistence of candidates to V5** — deferred (in-memory only this prompt).
- **Webpart content parsing** — deferred.
- **Auto-creation of new SourceLocation entries from candidates** — deferred (operator triage path).

## 10. Next Prompt Readiness

- Repo at expected baseline (HEAD `65b2c7c`).
- Working tree changes captured in §3.
- 325/325 scoped tests pass; ruff clean.
- All Phase 02 hard guardrails intact.
- Resolver's `LinkedSourceCandidate` model documented; deep-index opt-in remains a future explicit operation.
- CLI surface unchanged; `graph sources resolve` automatically surfaces new fields when a token is cached.

**Status: ready for Phase 02 — Prompt 06.**
