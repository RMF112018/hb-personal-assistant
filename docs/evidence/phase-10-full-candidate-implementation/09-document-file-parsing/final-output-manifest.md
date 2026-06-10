# Final Output Manifest — Document / File Parsing

## Intended operator-facing output

`hb-assistant files parse-index <paths…>`: a review-safe file parse **read-model index** — per file:
id, sanitized name, extension, MIME, parsed status, extraction method, text length + sha256 hash,
page/table/sheet counts, degraded reason, source refs, redaction flags — and never the extracted text.
Local-only, hash-only, no model, no writeback. JSON default; Markdown via `--no-json` / `--markdown-out`.

## Generated proof artifacts

| Artifact | Path | From | Safe? |
|---|---|---|---|
| Read-model index (MD) | `01-file-parse-final-output.md` | synthetic fixtures | yes |
| Read-model index (JSON) | `02-file-parse-final-output.json` | synthetic fixtures | yes |
| PDF proof | `03-pdf-or-supported-format-proof.json` | synthetic pdf | yes |
| DOCX proof | `04-docx-or-supported-format-proof.json` | synthetic docx | yes |
| XLSX proof | `05-xlsx-or-supported-format-proof.json` | synthetic xlsx | yes |
| Unsupported proof | `06-unsupported-format-proof.json` | `.xyz` fixture | yes |
| File-review consumption | `07-daily-brief-or-file-review-consumption-proof.md` | analysis | yes |
| No-raw-live-content | `08-no-raw-live-content-proof.txt` | read-model keys | yes |
| Safety scan | `09-safety-scan-results.txt` | scan | yes (0 findings) |
| Production DB unchanged | `10-production-db-unchanged-proof.txt` | sha256 | yes (unchanged) |
| Fixtures README | `fixtures/README.md` | — | yes (synthetic) |

## Manual verification command

```bash
hb-assistant files parse-index docs/evidence/phase-10-full-candidate-implementation/09-document-file-parsing/fixtures/note.txt --no-json
hb-assistant files parse-index <file1> <file2> --markdown-out /tmp/index.md --json
```
