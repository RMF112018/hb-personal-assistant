# File Parse Index (review-safe read-model)

_files: 6 · by status: {'parsed': 4, 'degraded': 1, 'unsupported': 1} · by extension: {'.txt': 1, '.md': 1, '.docx': 1, '.xlsx': 1, '.pdf': 1, '.xyz': 1} · local-only, hash-only, no model._

## Files
- **note.txt** (.txt · text/plain) → **parsed** via stdlib-text
  - id: file:59700155e034d16d · text_length: 60 · excerpt-hash: sha256:36481ad3cafc2ef2f47a536a7e2b391568b219343af9196c2e5a620c35d9060c · counts: —
- **spec.md** (.md · text/markdown) → **parsed** via stdlib-text
  - id: file:bc6661da34ecae62 · text_length: 55 · excerpt-hash: sha256:d57b2d3536f7c48bb983ee8326ff349daefc09a85197927e21e6575ff7c9f57a · counts: —
- **report.docx** (.docx · application/vnd.openxmlformats-officedocument.wordprocessingml.document) → **parsed** via python-docx
  - id: file:0eb2ecf5593ce953 · text_length: 73 · excerpt-hash: sha256:05a638fedf9485e366c3708a52831353f846364aef5eb6dd69d1e12bdd8642e5 · counts: table_count=1
- **budget.xlsx** (.xlsx · application/vnd.openxmlformats-officedocument.spreadsheetml.sheet) → **parsed** via openpyxl
  - id: file:f92e7414c873edfc · text_length: 328 · excerpt-hash: sha256:e0b46af56902ce3c6571204a361e22a2791f5bf8df93e8c90b5f50a90e90100c · counts: sheet_count=1
- **scan.pdf** (.pdf · application/pdf) → **degraded** via pdfplumber+pypdf
  - id: file:900db3ec3bae665c · text_length: 0 · excerpt-hash: (none) · counts: page_count=2, table_count=0 · degraded: scanned_pdf_no_text
- **archive.xyz** (.xyz · chemical/x-xyz) → **unsupported** via (none)
  - id: file:bd8611a628837654 · text_length: 0 · excerpt-hash: (none) · counts: — · degraded: unsupported_extension:.xyz
