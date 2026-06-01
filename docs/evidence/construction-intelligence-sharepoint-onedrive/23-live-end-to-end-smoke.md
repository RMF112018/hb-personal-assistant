# 23 — Live end-to-end files-pipeline smoke (SharePoint + OneDrive)

**Date:** 2026-06-01 · **HEAD (pre-commit):** `4c32122` · **Schema:** V24 · **Runtime:** Python 3.12
**Operator:** `bfetting@hedrickbrothers.com` (delegated)

The **first-ever live** SharePoint/OneDrive file-intelligence run with real SQLite **and** real Obsidian
writes (all prior runs were dry-run/mocked). Read-only against Microsoft 365 throughout — no writeback. Sources
+ bounds operator-approved: Tropical SharePoint + Business OneDrive, ≤50 items each, full pipeline including
the content-extract leg.

## Auth + a scope-minimization fix (required to proceed)

The live calls were initially blocked: the `graph files` commands (CLI **and** the resolver/discovery layer)
over-requested the broad scope set `['Sites.Read.All', 'Files.ReadWrite.All', 'User.Read']`. `Sites.Read.All`
is **not consented** for this delegated account (admin-restricted), so silent token acquisition failed even
after `hb-assistant auth login`. A token for `['Files.ReadWrite.All','User.Read']` succeeds. The Tropical
(`sharepoint_project_drive_folder`) and Business OneDrive (`onedrive_business_root`) sources are drive-scoped
and only need `Files.ReadWrite.All`.

**Fix (scope minimization — aligns with the repo's existing `scopes_for_source_kind` helper + its tests):**
- `cli/graph.py` — `crawl`/`index`/`delta`/`extract` now request `scopes_for_source_kind(<source>.kind)`;
  `onedrive` requests `GRAPH_SCOPES_DRIVE`. SharePoint site-page resolution paths keep the broad set.
- `construction/graph/resolver.py` — `_resolve_me_drive` (`/me/drive`) → `GRAPH_SCOPES_DRIVE`.
- `construction/graph/site_drive_discovery.py` — `_enumerate_me_drives` (`/me/drives`) → `GRAPH_SCOPES_DRIVE`.

This is a scope **reduction** (drops an unconsented, admin-restricted scope for drive sources); no consented
path regresses (the SharePoint site-page resolver — itself unconsented/unused here — still requests
`Sites.Read.All`).

## Live run — per-step results (all exit 0)

| Step | Command | Result |
|---|---|---|
| B | `graph files sources --apply` | V5 source projection (14 sources) |
| C1 | `graph files crawl --source <tropical> --apply --max-pages 2 --max-items 50 --max-seconds 60` | **live delta** `/drives/…/items/…/delta`; 50 items seen / **50 persisted**; 12 files, 38 folders; `truncated_by=max_items` |
| C2–4 | `project-match` / `ingestion-policy` / `review-queue` `--apply` | 12 files evaluated → **8 review_required + 4 metadata_only + 0 eligible** |
| C5 | `extract --apply --download --extract --max-bytes 5 MB` | **0 downloaded** (8 blocked review-required + 4 metadata-only) — guardrail held |
| D1 | `graph files onedrive --source <business> --apply` | OneDrive root **resolved live** (`drive_id` obtained, `drive_type=business`) |
| D2 | `graph files crawl --source <business> …` | live delta; 50 items seen / **50 persisted**; `truncated_by=max_items` |
| D3–5 | `project-match` / `ingestion-policy` / `review-queue` / `extract` `--apply` | 26 files → **26 low_confidence → review-routed; 0 eligible**; extract **0 downloaded** |
| E | `materialize/classify/match/evaluate/build-relationships/build-previews --apply` | document-intelligence chain re-applied (idempotent) |
| F1 | `graph files obsidian --apply` | real vault: 16 source manifests + project File Registers + Review summaries + Processing Receipt |
| F2 | `graph files document-obsidian --project tropical --apply` | real vault: **2 notes** (`07C_Document_Intelligence/Projects/tropical/Document Register.md`, `Review/tropical Document Review.md`) — first-ever 07C vault write |

### SQLite write-deltas (live DB, outside repo)

| Table | Before | After |
|---|---|---|
| `construction_drive_items` | 0 | **100** (50 SharePoint + 50 OneDrive, live-crawled) |
| `construction_review_queue` | 0 | **26** |
| `parser_outputs` | 0 | 0 (no eligible extraction) |
| `construction_document_cards` | 283 | 283 (chain reads the 06A `construction_drive_item_inventory` = 401; the V5 crawl layer and the card-inventory layer are parallel — see Note) |

**Obsidian:** 31 notes new/updated across `Work/HB Personal Assistant/07_File_Intelligence/` and the newly
created `…/07C_Document_Intelligence/`.

## Honest outcomes

- **0 content downloads** across both sources within the ≤50-item bound: every crawled file was sensitive/
  review-required (SharePoint) or low-confidence/unmatched (OneDrive) and was **correctly review-routed and
  skipped by extract**. This is the guardrail working as designed — not a failure. No real construction
  document was fetched. The live download → pdfplumber-parse path remains proven by the Prompt 01A unit tests
  + fixture; surfacing a live-eligible item would require a larger or folder-targeted crawl (deferred; the
  approved ≤50 bound was honored rather than expanded to force a download).
- **Note (layering):** `crawl`/`index` populate the V5 `construction_drive_items`; the document-card chain
  reads the 06A `construction_drive_item_inventory`. They are parallel layers, so this run's live crawl did
  not change the 283-card count. Wiring the V5 crawl output into card materialization is a recommended
  follow-up.

## Proofs (post-run)

- `graph files no-writeback-proof` → `ok=true`.
- `construction-agent data-quality no-writeback-proof` → `proof_passed=true`, `no_raw_values_persisted=true`.
- Forbidden-token scan of the 31 new/updated vault notes (Bearer / access_token / refresh_token /
  client_secret / downloadUrl / `sig=` / PEM / `deltatoken=` / `?token=`) → **0 matches**.
- Full suite after the scope edits: `pytest "not live and not integration and not manual"` **2080 passed**
  (exit 0); ruff / `mypy src` (176 files) / compileall clean.

## Guardrails honored

Read-only against M365 (only `/drives/…/delta`, `/me/drive`, `/me/drives` GETs); no writeback; downloads
bounded (≤5 MB) and gated by eligibility (0 occurred); cache (had any download run) lives outside repo+vault
and is deleted after parse; no full document text, signed/download URLs, tokens, secrets, or raw delta links
persisted to SQLite, vault, or this evidence; sensitive/low-confidence files never auto-extract; document
cards remain review-required (no auto-promotion); outputs advisory. Drive/site identifiers are resource IDs
(not secrets) and are truncated here.

## Follow-ups

1. Wire the V5 `construction_drive_items` crawl output into document-card materialization (currently reads the
   06A inventory layer).
2. Make the `graph files onedrive` CLI degrade gracefully to a structured `auth_required` payload instead of
   raising on token errors mid-discovery (it now succeeds with minimized scopes, but the handler is unguarded).
3. To exercise the live download + pdfplumber parse end-to-end, run a folder-targeted crawl over a
   non-sensitive, project-matched folder and confirm ≥1 `extraction_eligible` item.
