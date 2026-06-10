# Prompt 04 — Validation Results

| Check | Result |
|-------|--------|
| `compileall -q src tests` | OK |
| `pytest tests/test_phase_10_file_parse_read_model.py` | **5 passed** |
| `ruff check` (file_parse_read_model.py, files.py) | All checks passed |
| `mypy file_parse_read_model.py` | Success: no issues |
| Consumer proof grep | only the negative-assertion test line; no real consumer of `text_hash` |
| `parse-index --json` | emits `text_excerpt_hash` + `hash_scope: "text_excerpt"`, no `text_hash` |
| `parse-index --no-json` | emits `excerpt-hash: sha256:…` |
| Phase 09 evidence | renamed field + `hash_scope` in 7 files (authentic hashes preserved) |
| Production DB | not touched |
