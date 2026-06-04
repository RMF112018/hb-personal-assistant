# 116 — Phase 08D MCP Data-Quality Gates Evaluator

Status: Active · Phase: 08D Local MCP Bridge (Prompt 12) · Schema: V37

## Purpose

A deterministic, read-only gate evaluator that aggregates the Phase 08D MCP-bridge surfaces
into one advisory conformance report over the 14 gates declared in
`phase_08d_data_quality_gates_contract.json`, using the four-status taxonomy
(`pass` / `warning` / `fail_blocking` / `deferred_not_blocking`). It is the single advisory
view that shows the bridge is **structurally complete but not yet serveable**.

Mirrors the established Phase 08C gates shape in
`construction/second_brain/data_quality.py` (`_gate`, `_proof_gate`, `_count_gate_statuses`,
missing-evidence / readiness-overstatement helpers) and writes
`phase-08d-gates-proof.json` + `.md` to
`docs/evidence/construction-intelligence-phase-08d-mcp-bridge/`.

## Surface

- `evaluate_phase_08d_data_quality_gates(*, db_path=None)` — builds the 14 gates; read-only;
  persists nothing. Returns `ok`, `schema_version`/`_expected` (37), `contract_version`,
  `gates`, `by_field_status`, `status_counts`, `required_fields_covered`,
  `readiness_overstated`, plus the 08D-specific `ready_to_serve` and `serve_blockers`, and
  `guardrails`.
- `build_phase_08d_gates_proof(*, db_path=None, out_dir=None)` — evaluates, sets
  `proof_passed = ok and not readiness_overstated and not missing`, and writes the JSON + MD
  evidence (no-raw asserted on both via `_assert_no_raw`).
- CLI: `hb-assistant second-brain data-quality phase-08d-gates [--project] [--json/--no-json]`
  (a sibling of `phase-08c-gates` under `data_quality_app`).

## Key decision — registry/contract-level evaluation only

The evaluator evaluates every gate from registries, contracts, counts, and the **fast**
metadata-only proofs. It **never** dispatches the `hb_query` / `hb_research_packet` workflow
tools and **never** calls `build_mcp_allowed_tools_proof` / `build_mcp_resources_proof` —
those route through the synthesis/retrieval layer (slow, environment-dependent; ~6 min each
when the local model service is down) and are validated in their own prompts. This mirrors
the Prompt 10 audit redesign. A regression test monkeypatches both heavyweight proofs to
raise and asserts the evaluator still succeeds. Measured runtime: ~1 second.

## Gate mapping

| # | Gate | Signal (all fast) |
| --- | --- | --- |
| 1 | schema_contracts | schema == V37 (idempotent migrator) AND all ten 08D contracts loadable |
| 2 | server_config | permission-audit `server_config_safe` (stdio + foundation) |
| 3 | allowed_tools | `len(load_allowed_tools()) == 9` AND `allowed_registry_safe` |
| 4 | denied_tools | `denied_registry_complete` (all denied classes covered) |
| 5 | resources | `len(load_resources()) == 5` AND `resources_safe` |
| 6 | prompts | `len(load_prompts()) == 5` AND `prompts_safe` |
| 7 | receipts | `receipts_metadata_only` |
| 8 | denials | `build_mcp_tool_broker_proof` (deny-first, reason codes, denial receipts) |
| 9 | workflow_wrappers | `len(build_wrapper_registry()) == 9` |
| 10 | claude_desktop_config | `claude_config_safe` (preview only, never auto-written) |
| 11 | no_raw_access | **deferred_not_blocking** — proof artifact pending Prompt 13 |
| 12 | no_writeback | **deferred_not_blocking** — proof artifact pending Prompt 14 |
| 13 | policy_posture | overall permission-audit `proof_passed` (10 registry checks) |
| 14 | validation_matrix | **deferred_not_blocking** — full matrix pending Prompt 15 |

## No readiness overstatement

`no_raw_access`, `no_writeback`, and `validation_matrix` are the serve-readiness gates. Their
dedicated serve-blocking proof artifacts do not exist yet (Prompts 13/14/15), so the gates are
`deferred_not_blocking` — **never `pass`** — even though the permission audit's same-named
registry checks already pass. The gate tracks the proof artifact, not the registry signal.

Consequences enforced and tested:

- `ready_to_serve` is `False` (it requires all three readiness gates to be `pass`), with
  explicit `serve_blockers`: the three pending-prompt reasons plus `mcp_sdk_not_installed`.
- `readiness_overstated` is `False` by construction (a deferred gate is never `pass`).
- Deferred gates are `blocking=0`, so `ok` stays `True` and `proof_passed` is `True` — the
  proof asserts the bridge is correctly built and honestly deferred, not that it is serveable.
- Stop checks (all must be `False`): `gates_passed_with_missing_evidence`,
  `readiness_overstated`, `deferred_gate_reported_as_pass`.

## Posture

Local-first, read-only, advisory-only. No Microsoft 365 / Procore writeback, no raw stores /
files / payloads / SQL / URLs / prompts / responses exposed. The evaluator persists nothing;
it only writes the local evidence proof (no-raw asserted). `proof_passed` is `False` whenever
schema/contract/registry evidence is missing, any gate is `fail_blocking`, or readiness is
overstated.

## Deferred

- Gates 11/12/14 flip to `pass` only when their proof artifacts land in Prompts 13/14/15.
- The full Phase 08D pytest matrix (the heavyweight allowed/resources execution proofs)
  remains deferred to Prompt 15; this prompt runs the focused touched-surface subset plus the
  no-writeback proofs.
