# Prompt-preflight routing consistency — closeout evidence

## Tested SHAs

| Role | SHA | Notes |
| --- | --- | --- |
| **Behavioral closeout** | `e7744f3d` | Vault projection, schema args, discovery-first, full_loop fix |
| **Evidence hygiene** | `b41a0e48` and subsequent evidence-only commits | Docs/suite artifacts only after `e7744f3d` |
| **77-module batch (authoritative)** | `b41a0e48` | Same tree as `e7744f3d` for code; batch rerun after behavioral fix |
| **Baseline** | `05765b65` | `origin/main` audit point |

## Authoritative artifacts (use these for PR)

| File | Purpose |
| --- | --- |
| `suite-comparison-current.md` / `.json` | 77-module **node-ID** classification vs baseline |
| `suite-feature-batch-b41a0e48e4f7.txt` / `.json` | Feature offline batch at `b41a0e48` |
| `suite-baseline-batch-*.txt` / `.json` | Baseline offline batch |
| `route-proof-matrix.md` / `.json` | Expectation-based 20-case matrix (20/20) |
| `SUPERSEDED.md` | Index of historical artifacts |

## Exact-ID / has_exact_id coverage

Not in the 20-row route matrix; covered by unit tests:

- `tests/test_prompt_preflight_routing_consistency.py::test_decision_exact_id_populates_args`
- `tests/test_prompt_preflight_routing_consistency.py::test_decision_discovery_first_without_id`

## Feature failed nodes at b41a0e48 (all pre-existing on baseline)

- `tests/test_n8c23_mcp_surface_safety.py::test_n8c22_invariants_preserved`
- `tests/test_nas_mcp_tool_annotations.py::test_all_known_write_tools_are_marked_destructive`
- `tests/test_source_connector_eval.py::test_all_source_tools_have_disambiguating_descriptions`
- `tests/test_source_structure_cli.py::test_export_evidence_emits_gate_off_and_on_snapshots`

**Not failing:** `test_full_loop_and_manifest_refresh_via_mcp` (fixed at `e7744f3d`).
