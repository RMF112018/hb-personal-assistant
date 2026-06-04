# 113 — Phase 08D Claude Desktop Config and Runbook (Prompt 09)

**Baseline**: Post-08D-P08 at `ed2a8d2` (broker + tools + denied + resources + prompts). The safe config-preview surface already exists (Prompt 03); this prompt adds the operator runbook and the no-auto-write proof.

**Objective** (per prompt): Generate a safe Claude Desktop config preview and runbook proof; do not write the live Claude config automatically.

**Evidence**:
- `docs/evidence/construction-intelligence-phase-08d-mcp-bridge/mcp-claude-desktop-runbook-proof.md` + `mcp-claude-desktop-runbook-proof.json` (+ `claude-desktop-config-preview.json` from Prompt 03)
- `docs/runbooks/phase-08d-claude-desktop-configuration-runbook.md` (operator runbook)
- `docs/architecture/113-phase-08d-claude-desktop-config-and-runbook.md` (this)
- `tests/test_phase_08d_mcp_runbook.py`, extended `proof.py`, updated `__init__.py`

## Components
- **Operator runbook** (`docs/runbooks/phase-08d-claude-desktop-configuration-runbook.md`): the five operator steps (config-preview → verify safe/stdio/unsafe_reasons=[] → manual paste → restart → audit), the safe-vs-unsafe checklist, the live config path for manual paste, and the bold never-auto-write warning.
- **Runbook proof** (`proof.py::build_mcp_claude_desktop_runbook_proof()`): re-verifies the preview is `safe`/`schema_conformant`/`auto_apply=false`/stdio, and statically scans every mcp `.py` (excluding the prover) to confirm no reference to the live config filename `claude_desktop_config.json` or `Application Support/Claude` — proving the live config is never auto-written. Records the operator steps + safe checklist; writes `mcp-claude-desktop-runbook-proof.json`.

## No-auto-write model
The preview writes only the hyphenated, evidence-dir `claude-desktop-config-preview.json` and persists a metadata-only preview row; it never opens or writes the live config. The static scan (10 mcp files, 0 findings) makes this a verified invariant. The operator copies the validated `mcpServers` block in by hand.

## Boundary
No new CLI surface (Prompt 11); no audit surface yet (Prompt 10); no stdio exposure. `mcp_exposure` gate stays `deferred_not_blocking`.

## Validation
compileall exit 0; `ruff check` clean; `mypy src` clean (270 files; strict); `pytest -k phase_08d` green (incl. 4 new runbook tests); `build_mcp_claude_desktop_runbook_proof()` `proof_passed=true` (preview safe; no-auto-write 10 files / 0 findings); `config-preview` `safe=true`/`auto_apply=false`; 08A-08B / 08C / construction-agent no-writeback proofs all `proof_passed=true` (closed 08C bundle restored after). Full matrix deferred to Prompt 15.
