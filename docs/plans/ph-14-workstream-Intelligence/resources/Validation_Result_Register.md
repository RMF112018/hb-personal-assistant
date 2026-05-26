# Validation Result Register

| Date | Commit | Command | Exit Code | Result | Evidence File | Notes |
|---|---|---|---:|---|---|---|
| | | `.venv/bin/python -m pytest` | | | | |
| | | `.venv/bin/ruff check .` | | | | |
| | | `mypy src` | | | | |
| | | `hb-assistant diagnostics scan-sensitive --repo . --json` | | | | |
| | | `hb-assistant run morning --dry-run --json` | | | | |
