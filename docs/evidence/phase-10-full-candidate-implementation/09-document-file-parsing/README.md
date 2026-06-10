# Evidence — 09 Document / File Parsing

Candidate: `document-file-parsing` · Prompt: `prompts/09_document_file_parsing.md`
Branch: `experiment/phase-10-full-candidate-implementation` · Baseline: `0c75f4a7…`

## Scope

Added a review-safe document/file parse **read-model** (`files parse-index`) that runs the repo's
existing bounded local parsers (pdf/docx/xlsx/pptx/csv/txt/md/image/zip) and emits ONLY safe metadata
per file — id, name, extension, MIME, parsed status, extraction method, text length + sha256 hash,
page/table/sheet counts, degraded reason, redaction flags — never the extracted text. Local-only, no
network, no model, no writeback, no schema change. Parser deps verified to import from repo truth.

## What was NOT implemented

- No change to the existing parsers / router / ingestion service (reused as-is).
- No model-based classification (deterministic metadata only).
- No new dependencies (all parser libs already present and verified to import).
- No live document corpus — synthetic fixtures only.

## Files

`00-repo-truth-audit.md`, `fixtures/` (synthetic text fixtures + README),
`01/02-file-parse-final-output.{md,json}`, `03-pdf-…`, `04-docx-…`, `05-xlsx-…`,
`06-unsupported-format-proof.json`, `07-daily-brief-or-file-review-consumption-proof.md`,
`08-no-raw-live-content-proof.txt`, `09-safety-scan-results.txt`,
`10-production-db-unchanged-proof.txt`, `validation-commands.txt`, `validation-results.md`,
`final-output-manifest.md`, `changed-files.txt`, `branch-state.txt`.

## Safety checks

No extracted text in any read-model (hash-only). Synthetic fixtures only (no live document content).
No network, no model, no writeback. Safety scan: 0 findings. Production DB unchanged.

## Merge readiness

Merge-ready by itself: additive read-only read-model + CLI verb, fully tested (4 new tests; 545
targeted green), lint/type clean. One pre-existing unrelated failure documented.
