# 115 — Phase 08D MCP CLI and Operator Status (Prompt 11)

**Baseline**: Post-08D-P10 at `d50d955` (all MCP backing logic: registries, broker, wrappers, denied, resources, prompts, config/runbook, audit). This prompt exposes the operator CLI.

**Objective** (per prompt): Expose repo-consistent MCP CLI surfaces for status/config/tools/resources/prompts/audit/serve.

**Evidence**:
- `docs/evidence/construction-intelligence-phase-08d-mcp-bridge/mcp-cli-operator-proof.md`
- `docs/architecture/115-phase-08d-mcp-cli-and-operator-status.md` (this)
- `tests/test_phase_08d_mcp_cli.py`
- `src/hb_assistant/cli/second_brain.py` (four new `@mcp_app.command` wrappers)

## CLI (`second-brain mcp …`)
`status`, `config-preview`, `serve` existed (Prompt 03). This prompt adds four thin, read-only commands over the existing loaders/audit (no new backing logic):
- `tools` — lists `load_allowed_tools()` (name/wrapper/maps_to/risk/receipt_required) + `load_global_requirements()` + `load_denied_actions()`; snapshots the tool-registry.
- `resources` — lists `load_resources()` (uri/wrapper/source) + the resources-contract requirements; snapshots the resource-registry.
- `prompts` — lists `load_prompts()` (name/routes_through/forbidden) + the prompts-contract requirements; snapshots the prompt-registry.
- `audit` — runs `run_mcp_permission_audit(persist=…, write_evidence=False)`; emits the ten-check report (exit 0/3 on `proof_passed`).

All take `--json/--no-json` and `--snapshot/--no-snapshot`, following the Prompt 03 pattern (lazy import + JSON envelope).

## Model
- **List vs execute**: `tools`/`resources`/`prompts` LIST registry metadata (never dispatch tools, read content, or execute prompts); `audit` runs the fast registry-level permission audit.
- **Snapshot on list**: listing persists a metadata-only registry snapshot by default (`--no-snapshot` opts out); the audit persists its run.
- **Read-only / metadata-only**: no raw SQLite/SQL/files/Obsidian/Graph/Procore/writeback/URLs/prompts/responses/determinations. Denied-action *names* in the listing are policy metadata, not raw content.

## Boundary
No MCP data-quality gates (Prompt 12) or no-raw/no-writeback proofs (Prompts 13/14); serving stays fail-closed. `mcp_exposure` gate stays `deferred_not_blocking`.

## Validation
compileall exit 0; `ruff check` clean; `mypy src` clean (271 files; strict); `pytest tests/test_phase_08d_mcp_cli.py` **4 passed** (CliRunner: tools 9, resources 5, prompts 5, audit 10/10); `mcp --help` lists all seven commands; 08A-08B / 08C / construction-agent no-writeback proofs all `proof_passed=true` (closed 08C bundle restored after). Full matrix deferred to Prompt 15.
