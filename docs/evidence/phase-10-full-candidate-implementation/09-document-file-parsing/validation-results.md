# Validation Matrix — Document / File Parsing (Prompt 09)

| Area | Command / Method | Expected | Actual | Status |
|---|---|---|---|---|
| Dependency verification | `import pypdf, pdfplumber, docx, openpyxl, pptx, PIL` | all import | all import | ✅ |
| Compile | `compileall file_parse_read_model.py files.py` | pass | COMPILE_OK | ✅ |
| New regression | `pytest tests/test_phase_10_file_parse_read_model.py` | pass | 4 passed | ✅ |
| Targeted tests | `pytest -k "file or document or parse or extract or sharepoint or drive"` | pass (modulo pre-existing) | 545 passed, 1 pre-existing fail | ✅ |
| Lint | `ruff check <changed>` | pass | All checks passed | ✅ |
| Types | `mypy file_parse_read_model.py` | pass | no issues | ✅ |
| Read-model (txt/md) | synthetic fixtures | parsed, hash-only | `01`/`02` | ✅ |
| PDF proof | synthetic blank pdf | parsed, page_count=2 | `03` | ✅ |
| DOCX proof | synthetic docx | python-docx method | `04` | ✅ |
| XLSX proof | synthetic xlsx | openpyxl method | `05` | ✅ |
| Unsupported proof | `.xyz` | degraded honestly | `06` (unsupported) | ✅ |
| No raw live content | read-model keys | no text_excerpt; synthetic only | `08` | ✅ |
| Safety scan | forbidden-pattern scan | no findings | TOTAL_FINDINGS=0 | ✅ |
| Production DB checksum | sha256 before/after | unchanged (parsing touches no DB) | UNCHANGED=True | ✅ |
| DB migration | N/A | — | no schema change | ✅ N/A |

## Pre-existing failure (not this candidate)

`tests/test_phase_10_email_task_extraction.py::test_commitment_persists_to_commitment_table` fails in
this environment (matched on the `extract` keyword); confirmed pre-existing (fails with this candidate's
`files.py` change stashed). Untouched subsystem. Recorded, not fixed.

## Note

Parser dependencies were verified from repo truth (actual import) before use, per the plan correction.
Binary fixtures (docx/xlsx/pdf) are synthesized at generation time and NOT committed; only synthetic
text fixtures + the read-model proofs are committed.
