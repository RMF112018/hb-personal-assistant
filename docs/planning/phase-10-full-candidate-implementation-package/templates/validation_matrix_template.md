# Validation Matrix — <candidate-name>

| Area | Command / Method | Expected | Actual | Status |
|---|---|---|---|---|
| Compile | `python -m compileall src tests` | pass |  |  |
| Targeted tests | `<pytest command>` | pass |  |  |
| Lint | `<ruff command>` | pass or known unrelated failures |  |  |
| Types | `<mypy command>` | pass or known unrelated failures |  |  |
| DB migration | `<command or N/A>` | temp DB pass |  |  |
| Final output | `<command>` | artifact generated |  |  |
| Safety scan | `<command>` | no forbidden strings |  |  |
| Guard columns | `<command>` | zero |  |  |
| Production DB checksum | `<command>` | unchanged unless intentionally N/A |  |  |
