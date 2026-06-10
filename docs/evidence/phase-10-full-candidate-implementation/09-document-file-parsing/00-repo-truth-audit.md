# Repo-Truth Audit — Document / File Parsing (Prompt 09)

## Dependency verification (repo truth — done BEFORE use)

All parser deps were confirmed to actually import in the venv (not just declared in pyproject):
`pypdf 6.12`, `pdfplumber 0.11`, `python-docx 1.2`, `openpyxl 3.1`, `python-pptx 1.0`, `pillow 12.2`.
So pdf/docx/xlsx/pptx/csv/txt/md/image/zip are all locally supported.

## Existing surfaces (mature)

| Concern | Location | State |
|---|---|---|
| Parser router | `files/router.py` `ParserRouter` | Dispatches by extension to 8 bounded local parsers; failure isolation. |
| Parsers | `files/parsers/*.py` | Return `{text_excerpt, char_count, error?, failure_code?}` + format counts (page/table/sheet). |
| Ingestion service | `files/service.py` `FileIngestionService` | relevance → eligibility → approval → DL → hash → parse → persist. |
| File CLI | `cli/files.py` (`sample`, `ingest`) | Dry-run-safe. |

## Gap (Prompt requirement 3)

The parsers return `text_excerpt` (raw extracted content) — not review-safe for an index/evidence.
There was no read-model that emits ONLY safe metadata (id/name/ext/MIME/status/method/length+hash/
counts/degraded reason/refs/flags) with the extracted text excluded.

## Decision (surgical)

Add `file_parse_read_model.py` (`build_file_parse_read_model` + `build_file_index_read_model` +
renderer) that runs the existing local parsers and projects the result to a review-safe read-model —
text length + sha256 hash only, never the excerpt. New `files parse-index` CLI verb. Local-only, no
network, no model, no writeback, no schema change. Evidence uses synthetic fixtures only.
