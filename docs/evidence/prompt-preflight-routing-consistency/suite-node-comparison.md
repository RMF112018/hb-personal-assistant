### TARGETED ONLY (narrow module set)

This file covers a small module subset for quick triage.
**Authoritative 77-module node classification:** `suite-comparison-current.md` (feature SHA `b41a0e48`).

# Suite node comparison

- Feature SHA: `e7744f3d0789de6c93822a5e74e6256045770667`
- Baseline SHA: `05765b6512593d7383cfc6a2c1f6603ac3bbd215`
- Feature failed nodes: 2
- Baseline failed nodes: 3

## NEW (fail only on feature)

- *(none)*

## PRE-EXISTING (both)

- `tests/test_n8c23_mcp_surface_safety.py::test_n8c22_invariants_preserved`
- `tests/test_nas_mcp_tool_annotations.py::test_all_known_write_tools_are_marked_destructive`

## FIXED on feature

- `tests/test_n8c_final_validation.py::test_fresh_db_migrates_to_head`
