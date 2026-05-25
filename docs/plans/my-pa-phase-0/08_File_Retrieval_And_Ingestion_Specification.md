# File Retrieval and Ingestion Specification

Prepared: 2026-05-25

## Controls

```yaml
max_file_size_mb_default: 100
max_file_size_mb_pdf: 250
max_file_size_mb_office: 100
max_file_size_mb_cad_export_pdf: 300
warn_above_mb: 100
require_manual_approval_above_mb: 300
parse_timeout_seconds: 180
extraction_mode: bounded
ocr_enabled: false
```

## Pipeline

```text
metadata → relevance → eligibility → approval gate → download → hash → parse → persist parser output → source-linked summary
```

## Parser Matrix

| Family | Extensions | Parser | Guardrails |
| --- | --- | --- | --- |
| PDF | .pdf | PyMuPDF primary; pypdf fallback | Skip OCR and encrypted files; cap 250/300 MB. |
| DOCX | .docx | python-docx | No macros; text/tables only. |
| XLSX/XLSM | .xlsx/.xlsm | openpyxl/pandas | Values only; no macro execution; cap rows/sheets. |
| PPTX | .pptx | python-pptx | Extract slide text/notes; no media extraction by default. |
| CSV | .csv | Python csv/pandas | Dialect handling and row caps. |
| TXT/MD | .txt/.md | standard text reader | Encoding fallback and char caps. |
| Images | .png/.jpg/.webp | metadata only | No OCR. |
| ZIP | .zip | metadata only | No extraction without approval. |
| Native CAD/Revit | .dwg/.rvt/.rfa | unsupported | Out of MVP; exported PDFs only. |

## Failure Codes

unsupported_type, too_large, manual_approval_required, encrypted_or_password_protected, scanned_pdf_no_text, parser_timeout, parser_error, content_empty, download_forbidden, source_not_found.
