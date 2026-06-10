# 02 — Align CLI Human-Output Flags

## Goal
Make the runbook's human-readable operator commands executable by giving two Phase 10 commands the
paired `--json/--no-json` flag, matching the repo's read-model/report-surface convention.

## Change
Both commands **already rendered Markdown in their `else` branch** via
`render_file_index_markdown` / `render_hardened_mcp_packet_markdown`; they only declared
`typer.Option(True, "--json")`, which does not create a `--no-json` flag. The fix is the option
declaration only — no builder/renderer changes.

- `src/hb_assistant/cli/files.py` (`files parse-index`): `--json` → `--json/--no-json`.
- `src/hb_assistant/cli/second_brain.py` (`daily-brief mcp-packet`): `--json` → `--json/--no-json`.
- `--markdown-out` still writes the Markdown file regardless of stdout mode (unchanged).

## Tests
- `tests/test_phase_10_file_parse_read_model.py::test_cli_parse_index_no_json_emits_markdown`
- `tests/test_phase_10_mcp_packet_hardening.py::test_cli_mcp_packet_no_json_emits_markdown`
Both assert exit 0, the expected Markdown header, and that stdout is not JSON. Existing `--json`
tests remain green.

## Result
`--no-json` now prints `# File Parse Index …` and `# MCP Context Packet` respectively (see
`final-output-*.md`). The runbook's labeled "expected after Prompt 02" commands now work.
