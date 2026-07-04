# 06 — File type support

## Read support

Implemented in `src/hb_assistant/nas_mcp/file_readers.py` using `hb_assistant.files.parsers`:

| Extension | Reader | Behavior |
|---|---|---|
| `.txt`, `.md` | `TXTParser` | Bounded text excerpt |
| `.csv` | `CSVParser` | Bounded rows/chars |
| `.json` | inline | Parse validate + bounded text |
| `.yaml`, `.yml` | inline | Bounded text |
| `.pdf` | `PDFParser` | Bounded pages/chars (local parsers; no OCR) |
| `.docx` | `DOCXParser` | Bounded text |
| `.xlsx`, `.xls` | `XLSXParser` | Bounded sheets/rows |

Unsupported/binary: explicit deny or stat/list only via directory tools.

Allowlist: `NasMcpConfig.read_extensions` (default set in `config.py`).

## Write support (outputs sandbox only)

| Extension | Status | Implementation |
|---|---|---|
| `.txt` | **Implemented** | Direct write |
| `.md` | **Implemented** | Direct write |
| `.csv` | **Implemented** | Direct write |
| `.json` | **Implemented** | JSON validate + write |
| `.yaml`, `.yml` | **Implemented** | Direct write |
| `.docx` | **Implemented** | `python-docx` Document |
| `.xlsx` | **Implemented** | `openpyxl` Workbook |
| `.pdf` | **Deferred** | No safe PDF generator in repo |

Obsidian vault writes: **`.md` only** per Mac `allowed_write_file_types`.

## Local test evidence

| Test | Coverage |
|---|---|
| `test_work_read_only` | CSV read via `hb_root_read_file` |
| `test_output_sandbox_writes` | txt, md, csv, json write; unsupported ext denied |

## NAS functional proof

Deferred — no live MCP file-type probes on NAS.
