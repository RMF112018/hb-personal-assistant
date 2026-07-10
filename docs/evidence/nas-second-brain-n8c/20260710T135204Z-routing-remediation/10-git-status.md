# Git status at pre-deploy prep (2026-07-10)

```text
HEAD=dc523eaf34a1f959db2cdb1a45a15ac3327b0941
deployed_runtime=14dfc3a0e007475543e19f1d8efd999b23f3e28b
```

## Remediation files (representative — uncommitted at prep time)

**Modified (routing remediation):**

- `src/hb_assistant/obsidian_mcp/prompt_preflight.py`
- `src/hb_assistant/obsidian_mcp/workflow_recipe_manifest.py`
- `src/hb_assistant/nas_mcp/failure_envelope.py`
- `src/hb_assistant/nas_mcp/tool_registration.py`
- `scripts/generate-route-proof-matrix.py`
- `scripts/smoke-n8c-client-exposure.sh`
- `tests/test_*prompt_preflight*`, `tests/test_failure_envelope_routing.py`, exposure bridge tests

**New (routing remediation):**

- `scripts/run-audit-route-regression-matrix.py`
- `scripts/audit-route-regression-matrix.json`
- `scripts/route_proof_lib.py`
- `tests/test_prompt_preflight_modality_negation.py`
- `tests/test_prompt_preflight_argument_extraction.py`
- `tests/test_prompt_preflight_executability.py`
- `tests/test_prompt_preflight_semantic_equivalence.py`
- `tests/test_workflow_required_inputs_contract.py`

## Action required before image build

Land one commit containing the above (plus any doc/evidence updates intended for main). Deploy SHA must be that commit — not `dc523eaf` alone (missing remediation) and not `14dfc3a0` (currently deployed, pre-remediation).