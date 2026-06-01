# 44 — High-fidelity local PDF extraction (pdfplumber primary, pypdf fallback)

**Status:** Active (Prompt 01A). Additive parser upgrade; no schema change (V24).

## Why

A prompt requested integrating **LlamaParse** as the primary PDF engine to improve table/layout fidelity for
schedules, reports, and construction design documents. Repo-truth audit established that LlamaParse is a
**cloud API** that uploads source PDFs to `api.cloud.llamaindex.ai` and requires `LLAMA_CLOUD_API_KEY`. That
is incompatible with this repo's non-negotiable, enforced guardrails (and with the prompt's own guardrails):

- It would transmit Bobby's SharePoint/OneDrive construction documents (contracts, financials, personnel) to
  a third-party cloud — the single most-forbidden action here.
- It would break the enforced no-writeback / offline proofs: `tests/test_mutation_lockout.py` greps
  `src/hb_assistant/files` for `.post(`/network; `construction-agent data-quality no-writeback-proof` asserts
  `no_live_calls=true` and scans for `requests/httpx`-style network imports.
- It is unvalidatable offline (the default test suite is `not live`; no key/network).

Per the operator decision, the objective's *intent* (better table extraction, layout preservation,
structured output) is delivered with a **local, offline** engine instead.

## What changed

`src/hb_assistant/files/parsers/pdf.py` now selects an engine:

1. **Primary — `pdfplumber`** (local; pulls `pdfminer.six` + `pypdfium2`, both local). Iterates the first 5
   pages (existing bound); per page captures `extract_text()` (prose) **and** `extract_tables()` →
   serialized to bounded, single-line pipe-delimited rows under a `[table]` marker; concatenated into
   `text_excerpt` capped at `max_chars` (8000). Detects encryption (definitive failure) and empty/scanned
   (`scanned_pdf_no_text`).
2. **Fallback — `pypdf`** (unchanged original logic). Used when pdfplumber is unavailable (optional import
   guard) or raises an unexpected parse error.

The return value keeps the **same dict keys** downstream consumes (`text_excerpt`, `char_count`,
`failure_code`, `page_count`) plus additive metadata: `table_count` and `extraction_engine`
(`pdfplumber` | `pypdf_fallback`). `FileIngestionService` already forwards non-excerpt keys into
`parser_meta`, so no downstream change was needed. The `ParserRouter` and the seven other parsers (DOCX,
XLSX, PPTX, CSV, TXT/MD, Image, ZIP) are untouched.

## Measured improvement (synthetic fixture `tests/fixtures/sample_table.pdf`)

| Engine | table_count | char_count | structured row `A-300 | Structural Steel` |
|---|---|---|---|
| pdfplumber (primary) | 1 | 810 | preserved (`[table]` rows) |
| pypdf (fallback) | n/a | 539 | lost (flattened text) |

The ruled table survives as structured rows under pdfplumber and is flattened/lost under pypdf — the
fidelity gain the objective sought, achieved locally.

## Guardrails preserved

Fully local and offline — no upload, no API key, no network in the extraction path. pdfplumber/pdfminer
contain no `.post(`/network calls in our usage, so `test_mutation_lockout` and the no-writeback import scans
stay clean (`proof_passed=true`, `no_live_call_performed=true`, 0 mutating calls). Bounded excerpt
(≤ 8000 chars / first 5 pages) and downstream redaction (`ControlledExtractor._bounded_redact`, 2000 chars)
are unchanged; no full document text, signed/download URLs, tokens, or secrets are persisted. Output is
advisory; document cards remain review-required.

## Follow-ups

- Per-file engine/parser_version provenance is currently surfaced in `parser_meta` (CLI/record/evidence). To
  persist it, a future additive migration could add an `extraction_engine` column to `parser_outputs` /
  `construction_file_extraction_runs`.
- OCR for scanned PDFs (`scanned_pdf_no_text`) remains out of scope and local-only if pursued.

Evidence: `docs/evidence/construction-intelligence-phase-07c-document-intelligence/01a-llamaparse-integration.md`.
