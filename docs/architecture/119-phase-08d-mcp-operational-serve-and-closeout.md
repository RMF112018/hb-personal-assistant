# 119 — Phase 08D Operational MCP Serve + Validation-Matrix Closeout

Status: Active · Phase: 08D Local MCP Bridge (Prompt 15 — closeout) · Schema: V37

## Purpose

Prompt 15 turns the fail-closed MCP **foundation** into an **operational** local stdio MCP
server and closes Phase 08D. With the optional `mcp` Python SDK installed
(`pip install -e ".[mcp]"`), `hb-assistant second-brain mcp serve --stdio` runs a real
low-level MCP JSON-RPC server over the existing, audit-proven safe broker / resources /
prompts. The last data-quality gate (`validation_matrix`) is wired to a live proof so the
gates report **14 pass / 0 deferred**, and `ready_to_serve` becomes a truthful signal that
tracks real serve capability. Local stdio is the package's explicitly allowed transport; no
network listener is opened.

## Surface

- **Adapter** — `construction/second_brain/mcp/sdk_server.py`:
  - `build_mcp_app(*, db_path=None)` builds a low-level `mcp.server.lowlevel.Server` with one
    `build_default_broker(db_path, persist=True)` and registers handlers that map
    `list_tools`/`call_tool` → `ToolBroker.dispatch` (registered `validate_input=False` so the
    deny-first broker is the single authority and every call emits a metadata-only receipt),
    `list_resources`/`read_resource` → `read_resource`, and `list_prompts`/`get_prompt` →
    `render_prompt`. Lazy-imports the SDK so the base install stays SDK-free.
  - `serve_stdio_loop(*, db_path=None)` runs `stdio_server()` + `app.run(...)`; stdout is the
    JSON-RPC channel, diagnostics go to stderr.
- **Entrypoint** — `mcp/server.py:serve_stdio(*, db_path=None, dry_run=False)`: readiness-gated.
  Fail-closed (`served=False`) when a foundation check fails or the SDK is absent; `dry_run`
  reports readiness without entering the loop; otherwise it blocks, driving the real session,
  and returns `served=True` on clean disconnect.
- **CLI** — `second-brain mcp serve --stdio [--json] [--dry-run]`: `--dry-run` prints the
  readiness envelope to stdout (exit 0 iff ready); a real serve invocation keeps stdout clean
  (envelope to stderr only) and exits 0 if it served, 1 if fail-closed.
- **Gate proof** — `mcp/proof.py:build_phase_08d_validation_matrix_proof` /
  `evaluate_phase_08d_validation_matrix`: static, **SDK-agnostic** (no command execution, no
  wrapper dispatch). Verifies the `phase_08d_validation_matrix` contract + commands, dual-tree
  parity across both resource trees, and the closeout-critical evidence bundle. Writes
  `phase-08d-validation-matrix-proof.json` + `.md`.

## Gate + readiness honesty

`data_quality.evaluate_phase_08d_data_quality_gates` flips gate 14 from
`deferred_not_blocking` to `_proof_gate("validation_matrix", …)`. `serve_blockers` is computed
first and the optional-SDK blocker (`mcp_sdk_not_installed`) is appended **only when the SDK is
actually absent** (mirrors `policy.build_mcp_status`); `ready_to_serve` then requires no
`fail_blocking`, every readiness gate `pass`, **and** no serve blockers. Result: with the SDK
installed and all gates passing, `ready_to_serve` is honestly **True**; in a base install
without the SDK it is honestly **False** (`mcp_sdk_not_installed`) while the gates still report
14 pass / 0 deferred. No overstatement in either environment.

## Operational proof

- In-process round trip (`mcp.shared.memory.create_connected_server_and_client_session`):
  initialize; 9 tools / 5 resources / 5 prompts; allowed `hb_status` → metadata-only envelope +
  receipt; denied/unknown tool → denial + denial receipt; bounded resource/prompt payloads; no
  raw/token/URL/PEM marker in any payload — committed as `tests/test_phase_08d_mcp_serve_operational.py`
  (`pytest.importorskip("mcp")`, so the base suite skips it).
- End-to-end subprocess over real stdio pipes (`hb-assistant second-brain mcp serve --stdio
  --json`, temp DB migrated to V37): full round trip, receipts persisted (1 allow + 1 deny),
  serve envelope on stderr, client exit 0 — recorded in
  `docs/evidence/.../mcp-operational-serve-proof.md`.

## Posture / decisions

- Phase-scoped attestations are **not** retroactively flipped: the 08A `mcp_exposure` gate and
  the `mcp_implemented` markers in 08A-era proofs stay as historical phase-08A markers — the
  same convention by which `automation_hardening` remains `deferred_not_blocking` in the 08A
  gates even though 08B implemented it. The authoritative operational status lives in the
  **phase-08d-gates** evaluator (`ready_to_serve=True`), `mcp status`, and the operational
  serve proof — not in mutated 08A records.
- Fail-closed posture preserved: serving requires schema V37, all registries, the fail-closed
  permission policy, stdio-only transport, the Prompt 13/14 no-raw / no-writeback guard proofs,
  and the SDK. Attaching the server to the operator's Claude Desktop app remains a one-time
  manual paste of the (preview-only, never auto-written) config preview.

## Deferred

- None blocking. Phase 08D is closed. Remote/network MCP transport, desktop fleet rollout, and
  embeddings-backed semantic retrieval remain explicitly out of scope (Phase 09+).
