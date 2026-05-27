# Validation Matrix Template

| Command | Required | Exit Code | Status | Output |
|---|---:|---:|---|---|
| `.venv/bin/python -m pytest` | Yes | | | |
| `.venv/bin/ruff check .` | Yes | | | |
| `mypy src` | Yes | | | |
| `hb-assistant --version` | Yes | | | |
| `hb-assistant diagnostics env --json` | Yes | | | |
| `hb-assistant diagnostics paths --json` | Yes | | | |
| `hb-assistant diagnostics automation --json` | Yes | | | |
| `hb-assistant actions extract --dry-run --json` | Yes | | | |
| `hb-assistant actions list --json` | Yes | | | |
| `hb-assistant run morning --dry-run --json` | Yes | | | |
| `hb-assistant diagnostics scan-sensitive --repo . --json` | Yes | | | |
