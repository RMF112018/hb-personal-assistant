# Validation Matrix — Phase 10 Post-Merge Hardening

| Area | Command | Result |
|------|---------|--------|
| Compile | `compileall -q src tests` | OK (see compileall-results.txt) |
| Tests (named 3) | `pytest mcp_packet_hardening + file_parse_read_model + follow_up_watch_report` | **14 passed** (see test-results.txt) |
| New tests | `test_cli_mcp_packet_no_json_emits_markdown`, `test_cli_parse_index_no_json_emits_markdown`, `test_scan_does_not_persist_quality_flagged_items`, updated hash-contract assertions | all green (within the 3 files) |
| CLI smoke | parse-index `--no-json`/`--json`; mcp-packet `--no-json`/`--json` (temp DB) | exit 0; correct Markdown headers / JSON contract (see cli-smoke-results.md) |
| Lint (changed) | `ruff check` cli/files.py, cli/second_brain.py, follow_up_watch.py, file_parse_read_model.py | All checks passed |
| Types (changed) | `mypy` cli/files.py, cli/second_brain.py, file_parse_read_model.py | Success: no issues |
| Prod DB | sha256 before == after | UNCHANGED (production-db-unchanged-proof.txt) |
| Schema | migrations | none added (stays V45) |

## Changed-file lint/type note
Only the four files touched by this package were lint/type-checked (repo convention: scope is
partial — see CLAUDE.md). All are clean. No broad ruff/mypy run was needed; no new modules were
opted into strict scope. Pre-existing unrelated lint (e.g. cli/procore.py B008) is untouched.
