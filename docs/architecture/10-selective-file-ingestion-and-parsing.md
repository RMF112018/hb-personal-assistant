# 10 — Selective File Ingestion And Parsing

**Version**: 1.0.0 (Prompt 10)
**Status**: Complete
**Date**: 2026-05-25

## Overview

Prompt 10 completes the "selective" layer of the file/attachment ingestion pipeline for the HB Personal Assistant MVP.

Phase 9 delivered discovery skeleton, eligibility, downloader placeholder, PDF parser, and stub service. Phase 10 adds:

- Relevance scoring (heuristic, leveraging Phase 6 classification signals + filename/size/type heuristics)
- Full approval gate (manual_approval_required for >300MB or flagged; explicit allow-list for dry-run/CLI/tests)
- Complete ParserRouter + parsers for the full 08 matrix (PDF/DOCX/XLSX/XLSM/PPTX/CSV/TXT/MD + image/zip metadata-only)
- Real streaming download (GraphHttpClient retry + size guards + chunked to cache, no full body in memory)
- DriveItemClient.download_content convenience
- Updated FileIngestionService with full pipeline (relevance → eligibility → approval → conditional DL/hash/parse/persist + SourceLinkRegistry "parsed_from"/"attaches")
- Thin safe CLI (`diagnostics files sample`, `files ingest --dry-run`)
- Expanded tests + redaction/leak proofs
- Store query helpers for files/parser_outputs status

All outputs bounded/redacted (excerpts + metadata only); dry-run/mock friendly; no full file content logged/persisted/evidenced beyond bounded excerpts; read-only M365; honors 20/13/14/15/08/07/03/06 gates.

## Pipeline (from 08 spec)

```
metadata (Phase 9 discovery) 
  → relevance (Phase 10 scorer + Phase 6 signals)
  → eligibility (size/type/allow-list + 300MB manual flag)
  → approval gate (explicit ids or auto)
  → controlled streaming DL (if approved + not dry)
  → content hash (sha256)
  → bounded parse (ParserRouter + matrix, failure isolation)
  → persist (files + parser_outputs tables)
  → SourceLinkRegistry ("parsed_from", "attaches", etc.)
  → redacted excerpts + traces for Obsidian / later retrieval (Prompt 11)
```

## Key Components (Phase 10)

- `src/hb_assistant/files/relevance.py`: `FileRelevanceScorer` + `RelevanceScore` (Pydantic, redacted). Weighted: bobby_mention (+0.38), action/waiting (+0.28), attachment_context, name keywords (report/q3/fy/...), size bonuses/penalties. Threshold 0.22 for worth_ingesting.
- `src/hb_assistant/files/eligibility.py`: extended with `ApprovalGate` (approved_source_ids allow-list; is_approved()).
- `src/hb_assistant/files/parsers/`: full matrix (docx, xlsx, pptx, csv, txt, image, zip) + enhanced pdf (encrypted/scanned detection). All return consistent `{"text_excerpt", "char_count", ...?, "failure_code"?}`. Bounded (max_chars, row/slide caps). No OCR.
- `src/hb_assistant/files/router.py`: full ext dispatch + exception isolation to failure codes (08 list).
- `src/hb_assistant/files/downloader.py`: real `download()` using http streaming + guards.
- `src/hb_assistant/graph/http_client.py`: added `stream=True` support in _request + `download_to_file()` (Content-Length + chunked, max_bytes abort, retry policy).
- `src/hb_assistant/graph/drive_item_client.py`: `download_content()` convenience delegating to http.
- `src/hb_assistant/files/service.py`: `ingest_items()` full selective (with dry_run/approved/classifs), `discover_and_ingest_pending()` enhanced (best-effort via mail+attachments).
- `src/hb_assistant/store/repositories.py`: added `get_file`, `list_parser_outputs`, `get_files_by_status`.
- CLI: enhanced `diagnostics files sample`, new `cli/files.py` + wiring in `main.py` for `files ingest --dry-run --json` (exercises pipeline with samples + signals).
- Tests: expanded `test_file_ingestion.py` (relevance matrix, approval, multi-parser + bounds + errors + failure codes, full pipeline dry/real-mocked with links/persist, leak guards on excerpts/DB/artifacts).

## Parser Matrix (08 spec, implemented)

| Family | Extensions | Impl | Notes |
|--------|------------|------|-------|
| PDF | .pdf | pypdf (enhanced) | 5-page cap + chars; encrypted/scanned detection |
| DOCX | .docx | python-docx | paras + tables values; password detect |
| XLSX/XLSM | .xlsx/.xlsm | openpyxl (data_only, read_only) | row/col caps; no macro eval |
| PPTX | .pptx | python-pptx | slides + notes text; media skipped |
| CSV | .csv | stdlib csv + Sniffer | row cap, dialect |
| TXT/MD | .txt/.md | std text (utf8/latin1 fallback) | char cap |
| Images | .png/.jpg/.webp... | metadata only (no PIL) | type+size string |
| ZIP | .zip | stdlib zipfile | entry count + sample names (no extract) |

Failure codes (08): unsupported_type, too_large, manual_approval_required, encrypted_or_password_protected, scanned_pdf_no_text, parser_timeout (future), parser_error, content_empty, download_forbidden, source_not_found. Isolated per item; never abort whole batch.

## Integration

- **Phase 6**: classifications (bobby_mention, action/waiting) fed as signals to scorer (via discover or explicit in ingest_items).
- **Phase 5/7/9 Store + Links**: source_records (pre-created), files, parser_outputs, source_links ("parsed_from" etc via Registry).
- **Phase 8 Obsidian**: later writers can reference parser_outputs excerpts + links (via vault refs).
- **Graph**: read-only (Files.Read, Mail.Read etc delegated); streaming via http retry (Phase 2/6 policy).
- **CLI / run**: thin; full orchestration in future automation (Prompt 12+).
- **Schemas**: aligns with resources/sqlite-schema.sql (files, parser_outputs, source_links), email-classification, file-review.
- **Redaction**: all Pydantic/models excerpt-only; no full bodies/tokens/content in logs/DB/evidence; sensitive scan clean.

## Decisions & Tradeoffs (v1.0.0)

- Heuristic relevance (not ML) — fast, no deps, tunable; full triage in later (Prompt 10 model role "Triage").
- Approval as explicit allow-list in CLI/tests (no interactive prompt yet; real workflow Prompt 20?).
- No new heavy deps (python-pptx lightweight added; no pymupdf/ocr).
- Excerpts persisted to DB (for retrieval/synthesis) but bounded + source-linked; never full file.
- DriveItemClient download as convenience; downloader owns cache/policy.
- Mock-friendly everywhere; real DL only on approved + !dry + small sizes in tests.
- FK safety: callers ensure source_record exists before file/parser rows (enforced in tests via upsert).
- Version 1.0.0 manifest milestone after 0.9.0 foundation.

## Mermaid (Selective Pipeline)

```mermaid
flowchart TD
  subgraph Phase9
    Discover[Phase 9 discovery + metadata]
    Class[Phase 6 signals<br/>bobby_mention / action]
    Store[(Store)]
    Reg[SourceLinkRegistry]
  end
  subgraph SelectiveIngestion[Phase 10 Selective]
    Relevance[Relevance Scoring<br/>signals + size + type + name_kw]
    Gate[Eligibility + Approval Gate<br/>>300MB or flagged<br/>explicit approved ids]
    DL[Streaming Download<br/>GraphHttpClient retry + size guard<br/>to cache/*.bin]
    Parse[ParserRouter + bounded parsers<br/>PDF/DOCX/XLSX/PPTX/CSV/TXT<br/>image/zip metadata]
    Persist[Persist files + parser_outputs<br/>+ links parsed_from/attaches]
  end
  Discover --> Relevance
  Class --> Relevance
  Relevance --> Gate
  Gate -->|approved + !dry| DL
  DL --> Parse
  Parse --> Persist
  Persist --> Store
  Persist --> Reg
  Reg --> Links["parsed_from / attaches"]
  Note[Relevance first<br/>excerpts only (8k chars)<br/>failure isolation per item<br/>dry-run default] -.-> Gate
  CLI[files ingest --dry-run<br/>+ diagnostics files sample] --> Relevance
  CLI --> Gate
```

## Refs

- Prompt 10 objective + plan
- 02_Final_Implementation_Plan.md (row 8)
- 08_File_Retrieval_And_Ingestion_Specification.md (pipeline, matrix, controls, failures)
- 07_Local_Data_Model... (tables, FKs)
- 13/14/15/20 (redaction, dry-run, 20 gates, automation)
- 03/06 (Graph read-only, classification signals)
- 09 (foundation skeleton)
- resources/sqlite-schema.sql, email-classification.schema.json, parser matrix in 08
- Phase 9 architecture + evidence (patterns replicated)

## Next

Prompt 11: Retrieval, Embeddings, Workstream Context — consumes the selectively parsed excerpts + parser_outputs + links for semantic search / context assembly.

Guardrails honored: zero full content beyond excerpts, read-only, dry-run first, source-linked, redaction strong, tests green, v1.0.0 milestone.
