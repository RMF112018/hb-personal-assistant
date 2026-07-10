# Suite comparison (current — authoritative)

**Feature SHA:** `b41a0e48e4f7ee2358dd242ec8ec2eb43268138f`  
**Feature title:** docs(evidence): node-level suite comparison at final closeout HEAD  
**Baseline SHA:** `05765b6512593d7383cfc6a2c1f6603ac3bbd215`  

Scope: offline-safe module batch `test_prompt*`, `test_tool*`, `test_n8c*`, `test_nas*`, `test_source*`, `test_canonical*` (120s per-module timeout).

## Module summaries

| | Feature | Baseline |
| --- | ---: | ---: |
| pass modules | 73 | 69 |
| fail modules | 4 | 6 |
| timeout modules | 0 | 0 |
| total modules | 77 | 75 |
| duration_s | 988.8 | 960.1 |

## Node-level classification

### NEW (fail only on feature)

- *(none)*

### PRE-EXISTING (fail on both)

- `tests/test_n8c23_mcp_surface_safety.py::test_n8c22_invariants_preserved`
- `tests/test_nas_mcp_tool_annotations.py::test_all_known_write_tools_are_marked_destructive`
- `tests/test_source_connector_eval.py::test_all_source_tools_have_disambiguating_descriptions`
- `tests/test_source_structure_cli.py::test_export_evidence_emits_gate_off_and_on_snapshots`

### FIXED on feature (baseline fail, feature pass)

- `tests/test_n8c23_org_neutral_scan.py::test_client_tool_operating_manifest_is_org_neutral`
- `tests/test_n8c23_org_neutral_scan.py::test_new_source_modules_have_no_org_tokens_in_string_literals`
- `tests/test_n8c_final_validation.py::test_fresh_db_migrates_to_head`

## Superseded artifacts

The following are **historical only** and must not be used as current closeout truth:

- `suite-feature-head-ee06db39.txt` (pre-vault-projection fix; full_loop failed)
- `suite-comparison-head.md` (module-level summary at ee06db39)
- `suite-feature-batch.txt` / `suite-baseline-batch.txt` (earlier intermediate runs)

Targeted node comparison in `suite-node-comparison.md` covers a **narrow module set** for quick regression triage; this file is the authoritative 77-module node classification.

## Exact-ID / has_exact_id coverage (not in 20-row route matrix)

These cases are asserted in unit tests, not the offline route matrix:

- `tests/test_prompt_preflight_routing_consistency.py::test_decision_exact_id_populates_args`
  - Validated ID in prompt → getter arguments populated when getter is recommended
  - `has_exact_id=True` without extractable ID → no invented arguments
- `tests/test_prompt_preflight_routing_consistency.py::test_decision_discovery_first_without_id`
  - Broad topic prompt → list first; getter non-executable without ID

