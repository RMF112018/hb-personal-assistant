# 117 — Phase 08D No-Raw MCP Access Proof

Status: Active · Phase: 08D Local MCP Bridge (Prompt 13) · Schema: V37

## Purpose

A deterministic, read-only proof that **no MCP surface exposes raw content**. It scans every
surface the local stdio bridge presents and asserts none leaks raw stores, files, payloads,
SQL, signed/download URLs, tokens, raw prompts, or raw responses. The proof is wired into the
server startup checks so `no_raw_access_proof` flips **deferred → pass** and the
`no_raw_access_proof_pending_prompt_13` serve blocker drops. The bridge stays not-serveable
(`no_writeback_proof` → Prompt 14, and `mcp_sdk_not_installed` still block).

Lives in `construction/second_brain/mcp/proof.py`, reusing `_assert_no_raw` (the central
redaction scan in `financial_review_routing.py`), `_collect_keys`, `_FORBIDDEN_RESULT_FIELDS`,
`_guards_all_zero`, and `_GUARD_COLUMNS`.

## Surface

- `evaluate_no_raw_mcp_access(*, db_path=None, include_server_status=True, include_evidence_scan=True)`
  — scans the seven surfaces; read-only; persists nothing. Returns `{proof_passed, surfaces,
  scanned_surface_count, metadata_only, guardrails}`.
- `build_no_raw_mcp_access_proof(*, db_path=None, evidence_dir=None, write_evidence=True)`
  — wraps the full scan, `_assert_no_raw`s the serialized proof, writes
  `no-raw-mcp-access-proof.json` + `.md`.
- CLI: `hb-assistant second-brain mcp no-raw-access [--evidence/--no-evidence] [--json]`.

## Surfaces scanned

| Surface | Method (all fast, no wrapper dispatch) |
| --- | --- |
| registries | serialize `load_allowed_tools` / `load_denied_actions` / `load_global_requirements` → `_assert_no_raw` + forbidden-key check |
| resources | `load_resources()` static registry listing — **never** `read_resource` |
| prompts | `render_all_prompts()` static templates |
| receipts | self-contained temp-DB `PRAGMA`: no `raw_*` columns; hash columns present (`args_hash`/`result_hash`/`request_hash`); all 20 guard columns zero |
| config_preview | `build_claude_desktop_config_preview(persist=False, write_evidence=False)` → assert `env_values_persisted` False + `safe` True |
| server_status | `build_mcp_status(persist=False)` output (optional) |
| evidence | `_assert_no_raw` over each `*.json` under the 08D evidence dir (optional) |

`_scan_no_raw` records only `{surface, passed, detail}` — it never echoes the offending text
(on a hit it reports the matched *pattern* + surface label from the `_assert_no_raw` message).

## Key decisions

- **No heavyweight dispatch.** Resources/prompts are scanned at the registry/template level;
  the proof never calls `read_resource` or the `hb_query`/`hb_research_packet` wrappers (those
  route through retrieval/embedding, ~6 min when the model service is down). Receipts are
  introspected structurally via a temp DB. Measured runtime: ~0.8 s.
- **Recursion-safe startup wiring.** The full proof scans `build_mcp_status`, and the startup
  check calls the proof — so `evaluate_no_raw_mcp_access` exposes `include_server_status` /
  `include_evidence_scan` flags, and `policy.evaluate_startup_checks` calls it with **both
  False** (lazy import, no server-status surface) → no recursion, no disk scan. A failing
  no-raw scan sets `foundation_ok` False, which `server.py` already refuses on.
- **Gate 11 flipped (confirmed with user).** The Phase 08D data-quality gate `no_raw_access`
  now evaluates `build_no_raw_mcp_access_proof` via `_proof_gate` → `pass`, and the regenerated
  `phase-08d-gates-proof` reports 12 pass / 2 deferred. The gates proof's stale
  `deferred_gate_reported_as_pass` stop-check was replaced with `ready_to_serve_overstated`
  (`ready_to_serve` True while serve blockers remain — always False).

## Posture

Local-first, read-only, advisory-only. No writeback, no raw exposure, no resource dispatch.
`ready_to_serve` stays **False**: `no_writeback_proof` (Prompt 14) and the full
`validation_matrix` (Prompt 15) remain deferred, and `mcp_sdk_not_installed` is still a serve
blocker.

## Deferred

- `no_writeback_proof` startup check + gate stay deferred until Prompt 14.
- The full Phase 08D pytest matrix (heavyweight allowed/resources execution proofs) remains
  deferred to Prompt 15; this prompt ran the focused touched-surface subset + the no-writeback
  proofs.
