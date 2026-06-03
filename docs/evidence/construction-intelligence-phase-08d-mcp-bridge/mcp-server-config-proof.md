# Phase 08D — Prompt 03: MCP Server Foundation and Config Surface Proof

**Evidence artifact:** `docs/evidence/construction-intelligence-phase-08d-mcp-bridge/mcp-server-config-proof.md`
**Package manifest:** `HB_Construction_Intelligence_Phase_08D_Local_MCP_Bridge_Implementation_Package/00_PACKAGE_MANIFEST.md` · `v1.4.0-phase-08d-planning`
**Run date:** 2026-06-03 · **Base HEAD:** `1400744` · **Schema:** V37
**Scope:** Local **stdio-only** MCP server foundation + Claude Desktop config-preview surface + dependency decision. **No tools, resources, prompts, broker, or receipts** (Prompts 04–08); the server is **fail-closed and refuses to serve**.

---

## 1. Posture

Local-first, read-only, no-writeback, no-raw, advisory-only posture preserved. The MCP
layer opens **no socket and no network listener**, imports the `mcp` SDK only lazily
(never at import time), and persists **metadata only** (hashes, counts, transport,
redacted command, env *key names*, policy/schema version) with all twenty V37 guard
columns at 0. Nothing exposes raw SQLite, arbitrary SQL, raw files/Obsidian, direct
Graph/Procore, email/calendar mutation, source-system writeback, raw payloads,
signed/download URLs, raw prompts, or raw responses.

---

## 2. Dependency decision (08D-G02)

The official MCP Python SDK (`mcp`) is added as an **optional extra** in `pyproject.toml`
(`[project.optional-dependencies] mcp = ["mcp>=1.0"]`), **not** a core dependency. It is
**lazy-imported** only inside the serve entrypoint (`mcp/server.py::_import_mcp`), so the
base install, migrations, the full test suite, `mcp status`, `mcp config-preview`, and
every guard proof all run with **no MCP SDK present** (confirmed: `mcp_sdk_available=false`
in this environment). Transport is **stdio only**; if the SDK is absent (or the broker /
guard proofs are not yet wired) serving stays **fail-closed**.

---

## 3. Startup checks (`second-brain mcp status`)

`hb-assistant second-brain mcp status --json` → `foundation_ok=true`,
`ready_to_serve=false`, `mcp_sdk_available=false`, `mcp_tools_registered=0`.

| Check | Status |
|---|---|
| `schema_version_v37` | pass (schema=37) |
| `server_policy_seed_loaded` | pass (transport.allowed=[stdio]) |
| `allowed_tools_registry_present` | pass |
| `denied_tools_registry_present` | pass |
| `resource_registry_present` | pass |
| `prompt_registry_present` | pass |
| `permission_policy_fail_closed` | pass (all `allow_*` false) |
| `transport_stdio_only` | pass (http/sse/websocket/tcp/remote denied) |
| `no_raw_access_proof` | **deferred** → Prompt 13 |
| `no_writeback_proof` | **deferred** → Prompt 14 |

`serve_blockers`: `tool_broker_not_wired_prompt_04`, `no_raw_access_proof_pending_prompt_13`,
`no_writeback_proof_pending_prompt_14`, `mcp_sdk_not_installed`. A metadata-only row is
persisted to `second_brain_mcp_server_config_snapshots` (config_hash of the posture;
guards 0).

---

## 4. Serve is fail-closed (`second-brain mcp serve --stdio`)

`hb-assistant second-brain mcp serve --stdio --json` → `served=false`, exit code **1**.
`serve_stdio` runs the startup checks and refuses to serve (no tool broker, no guard
proofs yet); it **never opens a socket, loop, or network listener** and does not import
the SDK. This is the only reachable serve path at the foundation stage.

---

## 5. Claude Desktop config preview (`second-brain mcp config-preview`)

`hb-assistant second-brain mcp config-preview --client claude-desktop --json` →
`safe=true`, `schema_conformant=true`, `transport=stdio`, `unsafe_reasons=[]`,
`env_keys=[HB_MCP_POLICY, HB_MCP_TRANSPORT]`, `auto_apply=false`. The generated preview is
written to `claude-desktop-config-preview.json` and conforms to the shipped
`claude_desktop_config_preview.schema.json` (command const `hb-assistant`; args
`["second-brain","mcp","serve","--stdio","--json"]`). A metadata-only row is persisted to
`second_brain_mcp_claude_desktop_config_previews` (env **key names** only — never values).

**Safety gate** (`assess_config_safety`) flags: `unsafe_command` (command ≠ hb-assistant),
`unsafe_args` / `unsupported_transport` (argv not the exact stdio invocation),
`unsafe_env_key:<k>` (env key outside the `{HB_MCP_TRANSPORT, HB_MCP_POLICY}` allow-list),
and `broad_filesystem_path_in_env`. The implementation **never overwrites** the real Claude
Desktop config — preview only.

---

## 6. Validation commands + results

| Command | Result |
|---|---|
| `python -m compileall -q src tests` | exit 0 |
| `ruff check` (mcp module, CLI, test) | All checks passed |
| `mypy src` | Success — no issues in **264** source files (the new `mcp/` module is strict) |
| `pytest test_phase_08d_mcp_server + test_phase_08d_schema_v37 + test_phase_08d_contracts` | **17 passed** |
| `pytest -k "second_brain or phase_08d or mcp or cli_main or cli_smoke"` | **143 passed** |
| `second-brain mcp status --json` | `foundation_ok=true`, `ready_to_serve=false`, `mcp_sdk_available=false` |
| `second-brain mcp config-preview --client claude-desktop --json` | `safe=true`, `schema_conformant=true` |
| `second-brain mcp serve --stdio --json` | `served=false`, exit 1 (fail-closed) |
| `second-brain data-quality no-writeback-proof` | `proof_passed=true` |
| `second-brain data-quality phase-08c-no-writeback-proof` | `proof_passed=true` |
| `construction-agent data-quality no-writeback-proof` | `proof_passed=true` |

**Validation-subset rationale:** focused on the touched surfaces (the new MCP module +
CLI) plus the three no-writeback proofs, per the validation-minimum rule. Closed-phase
evidence churned by the proof runs was restored. The full matrix runs at Prompt 15.

---

## 7. Deferred / scope statement

- **Tool broker + workflow wrappers** → Prompt 04; **allowed tools** → Prompt 05;
  **denied actions** → Prompt 06; **resources** → Prompt 07; **prompts** → Prompt 08;
  **audit/receipts** → Prompt 10; **MCP no-raw-access proof** → Prompt 13;
  **MCP no-writeback proof** → Prompt 14.
- The server is **never `ready_to_serve`** at this stage; `serve` is fail-closed.
- `_AGENT_GUARDRAILS["mcp_implemented"]` stays **False** — no workflows are exposed yet
  (the `mcp_exposure` data-quality gate remains `deferred_not_blocking`).

**Verdict:** the stdio-only, fail-closed MCP server foundation, the dependency decision,
and the safe Claude Desktop config-preview surface are landed and green. Cleared for
Prompt 04 (MCP tool broker).
