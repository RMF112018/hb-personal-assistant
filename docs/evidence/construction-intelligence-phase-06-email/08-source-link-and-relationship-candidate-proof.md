# 08 — Attachment Metadata + Source-Link & Review Candidates

Phase 06 Prompt 08 · read-only / metadata-only · **no attachment content** · no mailbox mutation

Enriches attachment handling during indexing: metadata only (never content), detects SharePoint/OneDrive
links/filenames → creates **source-link relationship candidates**, and routes **sensitive attachment
hints** to the review queue. Integrated into the existing `index` flow (there is no separate
`attachments` command). The data feeds the later `relationships` and `review-queue` commands. The only
writes are local SQLite.

## What landed

- **`construction/email/attachment_analyzer.py`** (new, pure) — `analyze_attachment(name, content_type,
  is_inline)` classifies from name + content type only: `link_detected` (`.url`/sharepoint/onedrive
  name), `is_document` / `source_link_candidate` (non-inline document type), `sensitivity_hint` +
  `sensitivity_level` + `review_required` (filename matched against the 20 sensitivity categories), and
  a redacted `name_redacted` (`[redacted:hash].ext`). `detect_drive_links(text)` finds a
  SharePoint/OneDrive host in the bounded bodyPreview.
- **`construction/email/message_indexer.py`** — `_index_attachments` now enriches each attachment row
  (`name_redacted`, `sharepoint_or_onedrive_link_detected`, `sensitivity_hint`, `review_required`),
  creates a `*_drive_item` source-link candidate per document, enqueues an `email_review_queue` row per
  sensitive attachment, and (per message) creates a body-preview link candidate + review item. New
  counters surface in the `index` JSON; `relationship_candidates_created` + `review_items_created` are
  recorded on the crawl run.

## Reconciliation (package ↔ repo truth)

- **No new command** — attachment enrichment runs inside `index` (the validation matrix has no
  `attachments` command).
- **Detect from filename + content-type + bodyPreview, not `sourceUrl`.** The allowlist
  `attachment_metadata_select` is `id,name,contentType,size,isInline,lastModifiedDateTime`; Phase 06
  never blessed reference-attachment `sourceUrl`/`@odata.type`. Staying within the existing GET-only
  contract (no allowlist change) is the conservative choice; reference-attachment `sourceUrl` is a noted
  future enhancement.
- **Candidate types** = `sharepoint_drive_item` / `onedrive_drive_item`, `target_table=
  construction_drive_items`, `target_key=name_hash`/hashed-URL — actual drive-item resolution is Prompt
  09. **Sensitivity categories** mirror `email_sensitivity_review_categories.json` (20 categories,
  route-to-review-by-default), encoded as a keyword→category constant.

## Live validation — `graph mail index --project tropical --lookback-days 30 --max-messages 50 --json`

Exit 0. Counts: messages_indexed 102, **attachments_indexed 94**, attachments_with_link_hint 0,
**sensitive_attachments 5**, **source_link_candidates 22**, **review_items_created 6**.

Persisted-row inspection (operational DB, read-only query):

```
content-download / metadata-only guard:  SUM(content_downloaded)=0  MIN(metadata_only)=1  (ALL 94 rows)

sensitive attachment rows (names are hashes — no raw filenames):
  [redacted:817a…].pdf    application/pdf      lien_releases     review=1  link=0
  [redacted:d03b…].pdf    application/pdf      contracts         review=1  link=0
  [redacted:c9a9…].eml    message/rfc822      pay_applications  review=1  link=0
  [redacted:6a53…].docx   …wordprocessingml    contracts         review=1  link=0
  [redacted:0eea…].docx   …wordprocessingml    contracts         review=1  link=0

source-link candidates (email_relationship_candidates):
  sharepoint_drive_item   attachment_filename               21
  sharepoint_drive_item   sharepoint_link_in_body_preview    1

review queue (email_review_queue):
  contracts                            medium  3
  lien_releases                        medium  1
  pay_applications                     medium  1
  privileged_or_confidential_markers   medium  1     (= 6 total)
```

**Idempotent:** re-running `index` kept all three tables stable (attachments 94 / candidates 22 / review
6). Output + DB carry **counts and hashes only** — no raw filenames or URLs (leak scan: clean).

## Guardrails

- **No attachment content:** `content_downloaded=0` and `metadata_only=1` for all 94 rows; the analyzer
  reads `name`/`contentType` only; `$value` is never called; `$select` excludes `contentBytes`.
- **Read-only:** only `list_attachment_metadata` (guarded GET). **No write scope:** `Mail.Read` only.
- **Redaction:** filenames stored as `[redacted:hash].ext`; URLs reduced to host+hash evidence tokens.

## Verification

- `tests/test_attachment_analyzer.py` (document/inline/link/onedrive, 10 sensitivity-category fixtures,
  category-set ⊆ package, name redaction, bodyPreview link) + `tests/test_email_message_indexer.py`
  enrichment cases (link/sensitivity/candidate persistence, body-preview link candidate, idempotent
  enrichment) → pass. Lockout/guard/schema tests → green.
- `ruff check .` clean; `mypy src` no issues (124 files); `compileall` OK.
- Full safe subset green **except 4 pre-existing weekend-driven `test_automation.py` failures** (today,
  2026-05-30, is a Saturday; orchestrator skips weekends) — unrelated.

## Stop conditions — none triggered

No mailbox mutation, no `Mail.ReadWrite`/`Mail.Send`, no destructive migration, no full-body
persistence, and **no attachment-content download** (proven: 0/94).
