# Final Output — `files parse-index --no-json`

Command (temp/safe fixture):
```
python -m hb_assistant.cli.main files parse-index \
  docs/evidence/phase-10-full-candidate-implementation/09-document-file-parsing/fixtures/note.txt --no-json
```
Exit code: 0. Captured stdout (operator Markdown):
```
# File Parse Index (review-safe read-model)

_files: 1 · by status: {'parsed': 1} · by extension: {'.txt': 1} · local-only, hash-only, no model._

## Files
- **note.txt** (.txt · text/plain) → **parsed** via stdlib-text
  - id: file:59700155e034d16d · text_length: 60 · hash: sha256:36481ad3cafc2ef2f47a536a7e2b391568b219343af9196c2e5a620c35d9060c · counts: —
```

Notes:
- Before this prompt, `--no-json` was rejected (the option declared only `--json`). The Markdown
  render path already existed in the `else` branch; only the paired flag was missing.
- Output is raw-free: only basename, extension/MIME, status, extraction method, length, and a
  sha256 of the bounded excerpt (see Prompt 04 for the hash-scope clarification — captured here
  pre-Prompt-04, so the field still reads `hash:`).
