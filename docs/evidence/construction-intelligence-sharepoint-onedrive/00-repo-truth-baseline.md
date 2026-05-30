# 00 — Repo-Truth Baseline (Phase 06 SharePoint / OneDrive File Intelligence)

**Prompt:** Prompt 00 — Repo Truth Rebaseline and Graph Files Readiness Audit
**Date:** 2026-05-30
**Posture:** Audit only. No source, schema, scope, or runtime changes were made in this prompt.

This bundle establishes the authoritative starting point for HB Construction Intelligence
Phase 06 — SharePoint / OneDrive File Intelligence. Repo code, tests, runtime behavior, and
repo evidence are authoritative over the source package
(`HB_Construction_Intelligence_Phase_06_SharePoint_OneDrive_File_Intelligence_Package`).

---

## 1. Repository Identity

| Field | Value |
| --- | --- |
| Full name | `RMF112018/hb-personal-assistant` |
| Remote | `https://github.com/RMF112018/hb-personal-assistant.git` |
| Branch | `main` |
| HEAD | `0586885c864361b4ec8b1b5edd64c2c2768aa03e` |
| HEAD subject | `phase-06 prompt-14: final validation closeout and safety proofs` |

### Recent commits (most recent first)

```
0586885 phase-06 prompt-14: final validation closeout and safety proofs
99e9087 phase-06 prompt-13: add operational workflow validation and evidence chain
4a1b0dd update touched evidence outputs
6e9571a phase-06 prompt-12: add safe email obsidian projections
26c36f2 phase-06 prompt-11: commit remaining touched and related changes
2ad42a9 phase-06 prompt-11: encrypted-context structured email intelligence
819b7d6 feat(phase06): Prompt 10 email review routing + encrypted body eligibility (schema V13)
0168def feat(phase06): Prompt 09 email relationship candidates + graph mail relationships
e8a7db1 feat(email): store full message bodies via encrypted text vault
89c11f4 feat(phase06): Prompt 08 attachment metadata + source-link & review candidates
```

> **Naming note.** The completed work at HEAD is the **Phase 06 *Email* Intelligence** track
> (evidence under `docs/evidence/construction-intelligence-phase-06-email/`). The present package
> is a **separate Phase 06 *SharePoint / OneDrive File* Intelligence** track and gets its own
> evidence directory: `docs/evidence/construction-intelligence-sharepoint-onedrive/`.

### Working-tree status at audit start (pre-existing, not produced by this prompt)

```
 M docs/evidence/construction-intelligence-phase-06-email/13-operational-obsidian-preview.md
 M docs/evidence/construction-intelligence-phase-06-email/13-operational-review-queue-proof.md
 M docs/evidence/construction-intelligence-phase-06-email/13-operational-workflow-pilot-dry-run.json
 M docs/evidence/construction-intelligence-phase-06-email/13-operational-workflow-pilot-index-proof.md
 M docs/evidence/mvp-local-runtime/outputs/06-harness-success.marker
 M docs/evidence/mvp-local-runtime/outputs/scan-sensitive.json
 M docs/evidence/remediation/prompt-05-delegated-graph-proof/summary.json
?? .code-graph/
?? docs/evidence/construction-intelligence-phase-06-email/15-operator-runbook-and-handoff.md
?? docs/runbooks/
```

`git status --short -- src/ tests/` returned no output: **no source or test files were modified**
by this audit.

---

## 2. Module Readiness Inventory

Layered pipeline: **auth → Graph read clients → SQLite store + projections →
classification/retrieval → Obsidian output**, with `cli/` on top.

| Area | Status | Primary location | Phase 06 (files) readiness |
| --- | --- | --- | --- |
| Source registry | Exists | `construction/config/models.py`, `construction/config/loader.py`, `construction/fixtures/source_registry.py` | `SourceKind` covers `sharepoint_site`, `sharepoint_library`, `sharepoint_project_drive_folder`, `sharepoint_site_page`, `onedrive_personal_root`, `onedrive_business_root`, `onedrive_shared`, `onedrive_shared_library`, `procore_project`, `mailbox_deferred`. `DefaultPolicies` hard-pins `copy_originals_to_vault=False`, `store_full_text_in_vault_notes=False`. `SourceLocation.read_only: Literal[True]`. **Live registry validates: 6 projects / 14 sources.** |
| Auth | Exists / mature | `auth/providers.py`, `auth/scope_policy.py`, `config/models.py` (`IdentityConfig`) | MSAL delegated default + app-only cert provider. **Configured runtime delegated scopes are over-broad** — see §4. |
| Graph HTTP client | Exists / mature | `graph/http_client.py` | `GraphHttpClient`: token injection via getter, `get_all_pages()` paging with `max_pages`/`max_items` guards, retry (429/5xx), sanitized `GraphHttpError` (no Authorization/body/token leakage, 200-char truncation), `download_to_file()` bounded streaming with `max_bytes`. |
| Drive/file clients | Partial | `graph/drive_item_client.py`, `files/downloader.py` | `DriveItemClient` (`get_item`, `list_children`, `list_attachments`, `download_content`) is read/metadata + bounded download only — no batch/search/traversal helpers. `ControlledDownloader` streams to a bounded cache. |
| Resolver | Exists / comprehensive | `construction/graph/resolver.py` | `ConstructionGraphResolver` resolves all SharePoint/OneDrive source kinds to canonical IDs (`site_id`/`drive_id`/`folder_item_id`), with pre-resolved fast-path. Read-only; emits redacted `_redact_item_preview()`. Linked-source candidates carry `deep_index_allowed: Literal[False]`. |
| Delta crawler | Exists / operational | `construction/graph/delta_crawler.py` | `ConstructionDeltaCrawler` selects folder-/drive-/me-scoped delta endpoints, reads delta pages, persists delta token + crawl receipt, marks deleted items. Dry-run never writes SQLite. **Writes the narrow V2 inventory shape (`construction_drive_item_inventory`), not the richer V5 canonical `construction_drive_items` shape** — a known carry-forward gap. |
| File ingestion / parser router | Partial / stubbed | `files/`, V1 `parser_outputs` table | Download + bounded streaming exist; a wired parser router / extraction pipeline for SharePoint/OneDrive items is **not implemented**. |
| Store / SQLite schema | Exists / mature | `store/connection.py`, `store/migrator.py` | Additive, versioned. **Live `schema_version=14`** (per `construction-agent validate`). V2 inventory tables + V5 canonical construction index tables (`construction_drive_items`, `construction_source_locations`, `construction_source_sync_state`, `construction_source_crawl_runs`, `construction_processing_receipts`, `construction_document_cards`, …). Hard `CHECK` constraints enforce read-only / no-writeback (e.g. `construction_source_locations CHECK(read_only = 1)`; deferred-email-state `CHECK(mailbox_writeback_allowed = 0)`, `CHECK(persist_full_body = 0)`). |
| Obsidian manifests | Exists; file cards pending | `obsidian/writer.py`, `construction/manifests/{service,renderer,vault_writer,canonical_adapter,models}.py` | `MarkerBoundedWriter` is idempotent, marker-bounded, redacted, dry-run capable. `construction_document_cards` schema exists (V5). SharePoint/OneDrive **file**-card manifest integration is not yet wired. |
| Retrieval | Exists / lightweight | `retrieval/{context,embedder,retriever}.py` | Source-linked, redacted excerpts (truncated). SharePoint/OneDrive-derived excerpts are **not proven end-to-end**. |
| CLI | Exists; files group absent | `cli/main.py`, `cli/graph.py`, `cli/construction.py`, `cli/procore.py` | Root groups present. `hb-assistant graph` has **only the `mail` subgroup** — **there is no `graph files` (SharePoint/OneDrive) command group yet.** `construction-agent graph` exposes `auth status`, `sources resolve`, `delta` (resolver + delta crawler only). |

---

## 3. Baseline Validation Status

Run inside `.venv` (interpreter: **Python 3.14.5**).

| Check | Command | Result |
| --- | --- | --- |
| Byte-compile | `python -m compileall -q src tests` | **PASS** (exit 0) |
| Lint | `ruff check .` | **PASS** — "All checks passed!" |
| Type-check | `mypy src` | **PASS** — "Success: no issues found in 130 source files" |
| Config sanity | `hb-assistant construction-agent validate --json` | **PASS** — 4/4 checks (schema_version=14; 6 projects/14 sources; review rules v1 / 16 rules / threshold 0.7; model_routing default `llama3.2:1b`). Guardrails report `writeback: none`, `external_systems: read_only`, `metadata_only: true`. |
| Auth status | `hb-assistant auth status --json` | Returns a live token (see §4). |
| Safe Graph probe | `hb-assistant diagnostics graph --safe --json` | **PASS** — `GET /me` → 200, UPN present. App-support paths writable. |
| Test suite (default-safe subset) | `pytest -m "not integration and not live and not manual"` | **1549 selected · 1536 passed · 12 failed · 0 errors · 1 skipped** (38.4s). |

### Pre-existing test failures (NOT caused by this prompt — baseline condition)

All 12 failures trace to a single missing store method and are confined to the **email** track:

- `tests/test_email_classifier.py` — 7 failures
- `tests/test_automation.py` — 4 failures
- `tests/test_email_model_classifications_schema_v14.py` — 1 failure

**Root cause:** `construction/email/email_classifier.py:468` calls
`self._store.upsert_email_model_classification(...)`, but no such method is defined on
`ConstructionStore` (the schema-V14 `email_model_classifications` table exists in the migrator,
but the repository accessor was not added). This is a pre-existing regression in the Phase 06
*email* track at HEAD and is **out of scope** for the SharePoint/OneDrive file phase. It is
recorded here as a baseline so later prompts do not attribute it to file-intelligence work.
Per Prompt 00's audit-only posture and stop conditions, **no fix was applied.**

### `graph files` command surface — confirmed absent

```
$ hb-assistant graph files status --json
No such command 'files'.
```

The operator command surface required by the package
(`hb-assistant graph files {status,sources,sites,drives,onedrive,crawl,delta,index,
project-match,ingestion-policy,extract,obsidian,retrieve,no-writeback-proof}`) does **not** exist
yet. This is the primary implementation gap for the phase.

---

## 4. Deferred Risk — Over-Broad Microsoft Graph File Permissions

**This risk is explicitly deferred for Phase 06 and was NOT remediated in this prompt.**
No configured scope was removed, narrowed, or otherwise changed.

### Configured runtime delegated scopes (`config/models.py` `IdentityConfig.delegated_scopes`)

```
User.Read, Mail.Read, Calendars.ReadWrite.Shared, Files.ReadWrite.All, offline_access
```

`Files.ReadWrite.All` is **write-capable** and broader than the read-only file work this phase
performs. The resolver (`construction/graph/resolver.py:40,43`) likewise requests
`["Sites.Read.All", "Files.ReadWrite.All", "User.Read"]` (and a drive-scoped variant with
`Files.ReadWrite.All`).

### Active cached token observed via `hb-assistant auth status --json`

The currently cached token resolves as `token_type: app_only`, `classification: unexpected`
(UPN domain `@hedrickbrothers.com`), carrying a very broad consented scope set:

```
AllSites.FullControl, Calendars.Read.Shared, Calendars.ReadWrite.Shared,
Files.ReadWrite.All, Group.ReadWrite.All, Mail.Read, Mail.ReadWrite,
Sites.FullControl.All, Sites.Manage.All, Sites.ReadWrite.All, Sites.Selected,
User.Read, User.ReadBasic.All
```

These include write/management-capable file and site permissions
(`Files.ReadWrite.All`, `Sites.ReadWrite.All`, `Sites.Manage.All`, `Sites.FullControl.All`,
`AllSites.FullControl`). **No token, Authorization header, signed URL, raw delta link, or
secret value is recorded in this evidence** — only scope *names* and non-secret classification.

### Mitigation posture (behavior-level, in scope)

Tenant/application permission minimization is **deferred**. Per the package, this phase preserves
**behavior-level read-only operation** via defense-in-depth that is independent of the granted
scopes:

- YAML source policy + `SourceLocation.read_only: Literal[True]`;
- SQLite `CHECK(read_only = 1)` / `CHECK(mailbox_writeback_allowed = 0)` constraints;
- read-only Graph clients and a mutation-endpoint guard pattern (to be extended to files);
- dry-run-by-default workflows; `--apply`/`--download`/`--extract`/`--write-obsidian` gating;
- no mutation endpoints imported or called.

A standing remediation record will be carried as
`22-deferred-permission-tightening-record.md` at phase closeout.

---

## 5. Reconciliation: Package Claims vs. Repo Truth

| Package claim (02_REPO_TRUTH_AUDIT_SUMMARY / README) | Repo truth at HEAD `0586885` |
| --- | --- |
| Audited at commit `634fbb3…` (Phase 05 Procore closeout) | Repo has advanced well past that — HEAD is Phase 06 *email* prompt-14; live schema_version=14. The package's audited SHA is stale; this baseline supersedes it. |
| "MSAL delegated auth is the runtime default" | True (delegated provider is default), **but the active cached token is `app_only` / `unexpected`** and scopes are over-broad — deferred (§4). |
| "`ConstructionGraphResolver` can resolve SharePoint/OneDrive roots" | Confirmed present and comprehensive. |
| "`ConstructionDeltaCrawler` reads delta, persists tokens/receipts, marks deletes" | Confirmed; **writes V2 inventory shape, not V5 canonical** — gap stands. |
| "Obsidian manifest services produce manifests/receipts/cards" | Present; **file-card** integration for SharePoint/OneDrive not yet wired. |
| Operator `hb-assistant graph files …` command surface | **Does not exist yet** — entire `graph files` group is the implementation target. |
| Permission tightening | Confirmed deferred; documented in §4, not changed. |

---

## 6. Stop-Condition Check (Prompt 00)

No stop condition was triggered. This prompt made **no implementation changes**: no Microsoft 365
writeback was introduced, no permissions were tightened, no source files were copied into Obsidian,
no full source document text was persisted, no raw delta links were exposed, and no sensitive-file
review routing was bypassed. The over-broad-permission risk is documented and **deferred** per the
package's critical deferred scope.

## 7. Implementation Start Conditions (for Prompt 01+)

- Build the read-only Microsoft Graph **files** contract and a `graph files` CLI surface
  (status/sources/sites/drives/onedrive/crawl/delta/index/project-match/ingestion-policy/
  extract/obsidian/retrieve/no-writeback-proof), dry-run by default.
- Migrate delta-crawl persistence toward the V5 canonical `construction_drive_items` shape.
- Wire ingestion eligibility + sensitive review routing before any bounded extraction.
- Add file-card Obsidian manifests and prove source-linked SharePoint/OneDrive retrieval end-to-end.
- Carry the deferred permission-tightening risk forward; do not narrow scopes in this phase.
- Treat the 12 pre-existing email-track test failures as a separate, out-of-scope baseline.
