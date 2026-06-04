# Phase 08D — Prompt 09: Claude Desktop Config and Runbook Proof

**Evidence artifacts:** `mcp-claude-desktop-runbook-proof.md` (this) + `mcp-claude-desktop-runbook-proof.json` (generated) + `claude-desktop-config-preview.json` (from Prompt 03)
**Operator runbook:** `docs/runbooks/phase-08d-claude-desktop-configuration-runbook.md`
**Package manifest:** `HB_Construction_Intelligence_Phase_08D_Local_MCP_Bridge_Implementation_Package/00_PACKAGE_MANIFEST.md` · `v1.4.0-phase-08d-planning`
**Run date:** 2026-06-03 · **Base HEAD:** `ed2a8d2` · **Schema:** V37
**Scope:** Safe Claude Desktop config preview + operator runbook. **The implementation never writes the live Claude Desktop config automatically** — the operator copies the validated preview in by hand.

---

## 1. Posture

Local-first, read-only, stdio-only, advisory. The preview is generated for **manual paste
only** (`auto_apply=false`) and is written solely to the in-repo evidence dir
(`claude-desktop-config-preview.json`); the live config
(`~/Library/Application Support/Claude/claude_desktop_config.json`) is never touched by code.

---

## 2. Config preview safety (re-verified)

`build_claude_desktop_config_preview()` →
- `safe=true`, `schema_conformant=true`
- `transport=stdio`, `unsafe_reasons=[]`
- `auto_apply=false`
- `env_keys=[HB_MCP_POLICY, HB_MCP_TRANSPORT]`

The preview is exactly the safe `mcpServers` block (command `hb-assistant`; args
`["second-brain","mcp","serve","--stdio","--json"]`; env `HB_MCP_TRANSPORT=stdio`,
`HB_MCP_POLICY=local_safe`).

## 3. No-auto-write guarantee (static scan)

`build_mcp_claude_desktop_runbook_proof()` statically scans the mcp module source and
confirms **no code path references the live Claude Desktop config**:
- `live_config_never_written=true`
- `mcp_files_scanned=10`, `findings=[]` (no reference to `claude_desktop_config.json` or
  `Application Support/Claude` in any mcp `.py`; the prover module is excluded as the scanner).
- The only file the preview ever writes is the hyphenated, evidence-dir
  `claude-desktop-config-preview.json`.

## 4. Operator runbook (five steps)

1. `hb-assistant second-brain mcp config-preview --client claude-desktop --json`
2. Confirm `safe=true`, `transport=stdio`, `unsafe_reasons=[]`, `auto_apply=false`.
3. Copy the preview **manually** into `~/Library/Application Support/Claude/claude_desktop_config.json`.
4. Restart Claude Desktop.
5. `hb-assistant second-brain mcp audit --json` (audit surface lands in Prompt 10) to confirm posture.

Safe-vs-unsafe checklist (command=`hb-assistant`, transport=stdio, args exact, env keys ⊆
`{HB_MCP_TRANSPORT, HB_MCP_POLICY}`, no secrets/broad filesystem path) is documented in the
runbook; `unsafe_reasons` names any violation and the operator stops.

---

## 5. Validation commands + results

| Command | Result |
|---|---|
| `python -m compileall -q src tests` | exit 0 |
| `ruff check` (proof + test) | All checks passed |
| `mypy src` | Success — no issues in **270** source files (strict) |
| `pytest test_phase_08d_mcp_runbook + server + prompts` | **4 + … passed** (full 08D suite green) |
| `build_mcp_claude_desktop_runbook_proof()` | `proof_passed=true`; preview safe; no-auto-write scan 10 files / 0 findings |
| `second-brain mcp config-preview --client claude-desktop --json` | `safe=true`, `transport=stdio`, `auto_apply=false` |
| `second-brain data-quality no-writeback-proof` | `proof_passed=true` |
| `second-brain data-quality phase-08c-no-writeback-proof` | `proof_passed=true` |
| `construction-agent data-quality no-writeback-proof` | `proof_passed=true` |

**Validation-subset rationale:** focused on the runbook/preview surface + the three
no-writeback proofs, per the validation-minimum rule. Closed-phase evidence churned by the
proof runs was restored. Full matrix at Prompt 15.

---

## 6. Deferred / scope statement

- **Audit surface** (`mcp audit`): Prompt 10; **CLI surfaces**: Prompt 11; **MCP data-quality
  gates**: Prompt 12; **MCP no-raw-access / no-writeback proofs**: Prompts 13/14.
- Serving over stdio is still fail-closed (guard proofs + optional SDK). `mcp_implemented`
  stays False; `mcp_exposure` gate `deferred_not_blocking`.

**Verdict:** the Claude Desktop config preview is safe + preview-only, the live config is
provably never auto-written, and the operator runbook documents the manual five-step flow.
Cleared for Prompt 10 (audit/permission agent).
