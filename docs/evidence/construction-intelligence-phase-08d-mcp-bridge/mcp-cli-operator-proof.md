# Phase 08D — Prompt 11: MCP CLI and Operator Status Proof

**Evidence artifact:** `mcp-cli-operator-proof.md` (this)
**Package manifest:** `HB_Construction_Intelligence_Phase_08D_Local_MCP_Bridge_Implementation_Package/00_PACKAGE_MANIFEST.md` · `v1.4.0-phase-08d-planning`
**Run date:** 2026-06-04 · **Base HEAD:** `d50d955` · **Schema:** V37
**Scope:** Expose repo-consistent MCP operator CLI surfaces. `mcp status`/`config-preview`/`serve` already existed (Prompt 03); this prompt adds `mcp tools`/`resources`/`prompts`/`audit` as thin read-only JSON wrappers over the existing loaders/audit.

---

## 1. Posture

Local-first, read-only, metadata-only. The list commands surface registry metadata (names,
wrappers, URIs, routing) — never dispatch tools, read resource content, or execute prompts.
`mcp audit` runs the (fast, registry-level) permission audit. No command exposes raw SQLite,
arbitrary SQL, raw files/Obsidian, direct Graph/Procore, writeback, raw payloads,
signed/download URLs, raw prompts/responses, or determinations. Snapshots persisted on list
are metadata-only (counts + hashes, guards 0).

---

## 2. The seven MCP CLI surfaces

| Command | Behaviour | Persistence |
|---|---|---|
| `mcp status` | server-foundation posture (counts, blockers) | server-config snapshot (`--no-snapshot`) |
| `mcp config-preview --client claude-desktop` | safe Claude Desktop preview (never auto-applied) | preview snapshot + evidence JSON |
| `mcp tools` | **list** the 9 allowed tools + 27 denied actions + global requirements | tool-registry snapshot (`--no-snapshot`) |
| `mcp resources` | **list** the 5 resources (uri/wrapper/source) + requirements | resource-registry snapshot |
| `mcp prompts` | **list** the 5 prompts (name/routes_through/forbidden) + requirements | prompt-registry snapshot |
| `mcp audit` | **run** the 10 permission-audit checks | permission-audit run (`--no-snapshot`) |
| `mcp serve --stdio` | fail-closed (no socket; exits 1) | none |

All list/audit commands take `--json/--no-json` and `--snapshot/--no-snapshot`.

---

## 3. Validated outputs

| Command | Result |
|---|---|
| `mcp tools --no-snapshot --json` | `allowed_tool_count=9`, `denied_action_count=27`, 7 global requirements; e.g. `hb_status -> mcp_status_wrapper` |
| `mcp resources --no-snapshot --json` | `resource_count=5`, 5 requirements; first `hb://status/system` |
| `mcp prompts --no-snapshot --json` | `prompt_count=5`; e.g. `review_today_brief -> [hb_get_daily_brief, hb_validation_status]` (every `routes_through` ⊆ the 9 allowed) |
| `mcp audit --no-snapshot --json` | `proof_passed=true`, `status=ok`, `finding_count=0`, 10/10 checks |
| `mcp --help` | lists all seven commands |

---

## 4. Validation commands + results

| Command | Result |
|---|---|
| `python -m compileall -q src tests` | exit 0 |
| `ruff check` (CLI + test) | All checks passed |
| `mypy src` | Success — no issues in **271** source files (strict) |
| `pytest tests/test_phase_08d_mcp_cli.py` | **4 passed** (CliRunner) |
| `second-brain data-quality no-writeback-proof` | `proof_passed=true` |
| `second-brain data-quality phase-08c-no-writeback-proof` | `proof_passed=true` |
| `construction-agent data-quality no-writeback-proof` | `proof_passed=true` |

**Validation-subset rationale:** focused on the CLI surface + the three no-writeback proofs,
per the validation-minimum rule. Closed-phase evidence churned by the proof runs was restored.
Full matrix at Prompt 15.

---

## 5. Deferred / scope statement

- **MCP data-quality gates** (`mcp data-quality phase-08d-gates`): Prompt 12;
  **MCP no-raw-access / no-writeback proofs** (`mcp data-quality …`): Prompts 13/14.
- The CLI is read-only; serving over stdio stays fail-closed. `mcp_implemented` stays False;
  `mcp_exposure` gate `deferred_not_blocking`.

**Verdict:** the seven repo-consistent MCP operator CLI surfaces are live, read-only, and
metadata-only. Cleared for Prompt 12 (MCP data-quality gates).
