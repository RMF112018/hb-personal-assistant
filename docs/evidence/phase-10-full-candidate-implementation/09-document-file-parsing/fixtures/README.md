# Synthetic fixtures — Phase 10 document/file parsing

All fixtures are **synthetic** (no live/sensitive document content).

- `note.txt`, `spec.md` — committed synthetic text fixtures.
- `report.docx`, `budget.xlsx`, `scan.pdf` — synthesized at evidence-generation time in a temp dir (python-docx / openpyxl / pypdf) and parsed into read-models; the binaries are **not committed** (the read-model proofs in `03/04/05` carry only safe metadata).
- `archive.xyz` — synthetic unsupported-extension fixture (degraded-honesty proof `06`).

Parser dependencies were verified to import from repo truth before use: pypdf, pdfplumber, python-docx, openpyxl, python-pptx, pillow.
