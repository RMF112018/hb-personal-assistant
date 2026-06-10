# Validation Matrix — Local Model Routing Refinement (Prompt 05)

| Area | Command / Method | Expected | Actual | Status |
|---|---|---|---|---|
| Compile | `compileall model_diagnostics.py second_brain.py` | pass | COMPILE_OK | ✅ |
| New regression | `pytest tests/test_phase_10_model_routing_diagnostics.py` | pass | 5 passed | ✅ |
| Targeted tests | `pytest -k "model_router or model_eval or structured_output or local_model or daily_brief_intelligence or model_diagnostics"` | pass | 87 passed | ✅ |
| Lint | `ruff check <changed>` | pass | All checks passed | ✅ |
| Types | `mypy model_diagnostics.py` | pass | no issues | ✅ |
| Diagnostics (present) | `build_routing_diagnostics` | all available | 7/7 available | ✅ |
| Diagnostics (unreachable) | daemon unreachable | all fail-closed, no cloud | 7/7 blocked, no_cloud | ✅ |
| Fallback | primary model missing | deterministic local fallback | relationship_scoring → selected_fallback | ✅ |
| Eval summary | `run_model_eval(synthetic)` | decisive summary | ok=true | ✅ |
| Schema-failure | structured-output validation | schema_valid metric | covered (eval + structured_output tests) | ✅ |
| No-cloud | 3 probes + config guardrail | no_cloud everywhere | no_cloud_all=true | ✅ |
| No-raw-persistence | receipts table introspection | hash-only, no raw cols, guards | no raw cols; 13 guards | ✅ |
| Safety scan | forbidden-pattern scan | no findings | TOTAL_FINDINGS=0 | ✅ |
| Production DB checksum | sha256 before/after | unchanged | UNCHANGED=True | ✅ |
| DB migration | N/A | — | no schema change | ✅ N/A |

Notes: diagnostics are deterministic given the model probe; offline `--mock` shape works without a
daemon. The eval harness + structured-output client (existing) enforce schema validation, low-confidence
handling, and hash-only receipts; this candidate adds the consolidated diagnostics surface over them.
