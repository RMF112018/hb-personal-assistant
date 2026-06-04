# 118 — Phase 08D No-MCP-Writeback Proof

Status: Active · Phase: 08D Local MCP Bridge (Prompt 14) · Schema: V37

## Purpose

A deterministic, read-only proof that **no MCP surface can perform writeback, a direct
Graph/Procore/SQL API call, or external delivery**. It is wired into the server startup
checks so `no_writeback_proof` flips **deferred → pass** and the
`no_writeback_proof_pending_prompt_14` serve blocker drops. With both guard proofs now live
(no-raw-access landed in Prompt 13), `_DEFERRED_SERVE_BLOCKERS` is empty and the optional MCP
SDK (`mcp_sdk_not_installed`) is the sole remaining serve gate; `serve` still refuses at the
foundation stage and the data-quality gates still report not-ready (`validation_matrix`
deferred to Prompt 15).

Lives in `construction/second_brain/mcp/proof.py` next to the no-raw proof, reusing
`_assert_no_raw`, `_guards_all_zero`, `_GUARD_COLUMNS`, and `_scan_no_raw`.

## Surface

- `evaluate_no_writeback_mcp_access(*, db_path=None, include_server_status=True, include_evidence_scan=True)`
  — scans the surfaces; read-only; persists nothing. Returns `{proof_passed, surfaces,
  scanned_surface_count, metadata_only, guardrails}`.
- `build_no_mcp_writeback_proof(*, db_path=None, evidence_dir=None, write_evidence=True)`
  — wraps the full scan, `_assert_no_raw`s the serialized proof, writes
  `no-mcp-writeback-proof.json` + `.md`.
- CLI: `hb-assistant second-brain mcp no-writeback [--evidence/--no-evidence] [--json]`.

## Surfaces scanned

| Surface | Method (all fast, no wrapper dispatch) |
| --- | --- |
| permission_policy | `_load_seed(_PERMISSION_POLICY_SEED)` — every `allow_*` flag false (fail-closed) |
| denied_registry | `load_denied_actions()` ⊇ writeback ∪ direct-API ∪ URL action classes |
| tool_wrappers | `build_wrapper_registry()` == 9 + `global_requirements` ⊇ `{workflow_wrapper_only, no_writeback}` |
| receipts | self-contained temp-DB `PRAGMA`: writeback/API guard columns present at CHECK(=0); all 20 guard columns zero |
| config_preview | `build_claude_desktop_config_preview(persist=False, write_evidence=False)` → `auto_apply` False + `preview_only_no_auto_apply` |
| server_guardrails | `build_mcp_status(persist=False)` → `no_external_writeback` / `no_direct_graph_or_procore` / `no_arbitrary_sql` True (optional) |
| evidence | `_assert_no_raw` over each `*.json` under the 08D evidence dir (optional) |

## Key decisions

- **No heavyweight dispatch / recursion-safe.** Mirrors the Prompt 13 design: static/structural
  scans only (no `read_resource`, no `hb_query`/`hb_research_packet`); receipts via a temp-DB
  PRAGMA. The full proof scans `build_mcp_status`, and the startup check calls the proof — so
  the evaluator exposes `include_server_status` / `include_evidence_scan` flags and
  `policy.evaluate_startup_checks` calls it with both **False** (lazy import). Measured
  runtime: ~0.6 s.
- **Gate 12 flipped (precedent from Prompt 13).** The Phase 08D data-quality gate
  `no_writeback` now evaluates `build_no_mcp_writeback_proof` via `_proof_gate` → `pass`; the
  regenerated `phase-08d-gates-proof` reports 13 pass / 1 deferred.
- **`_DEFERRED_SERVE_BLOCKERS` is now empty.** No guard proof remains deferred; the SDK is the
  only serve gate, appended in `build_mcp_status` when the optional `mcp` package is absent.

## Posture

Local-first, read-only, advisory-only. No writeback, no direct Graph/Procore/SQL, no external
delivery. `ready_to_serve` stays **False**: the full `validation_matrix` (Prompt 15) remains
deferred in the gates, `mcp_sdk_not_installed` blocks the server, and `serve` refuses at the
foundation stage regardless. No overstatement.

## Deferred

- `validation_matrix` gate stays deferred until the Prompt 15 closeout.
- The full Phase 08D pytest matrix (heavyweight allowed/resources execution proofs) remains
  deferred to Prompt 15; this prompt ran the focused touched-surface subset + the no-writeback
  proofs.
