# Repo-Truth Audit — Local Model Routing Refinement (Prompt 05)

## Existing surfaces (mature)

| Concern | Location | State |
|---|---|---|
| Router | `…/local_ai/model_router.py` `route_task_family` → `RouteResult` | Deterministic, fail-closed, never cloud; per-family decision with profile/model/availability/blockers/reason_code/considered chain/no_cloud. |
| Profiles + routing config | `resources/config/phase_10_local_model_profiles.seed.yaml`, `local_model_task_routing.seed.yaml` | 7 task families → profiles; fallback chains; guardrails (local_only/no_cloud/no_raw_persistence). |
| Provider probe | `provider.py` `build_local_model_status`; CLI `_local_model_present` | Read-only Ollama `/api/tags` probe; redacted errors. |
| Structured output | `structured_output.py` `StructuredOutputClient.run` → `StructuredOutputResult` | Schema-validated; hash-only receipt (`local_model_run_receipts`, no raw columns + 13 guards). |
| Eval harness | `model_eval.py` `run_model_eval` | Offline synthetic + live; decisive per-family recommendation + reason codes. |
| CLI | `local-model status/profiles/route/eval` | Each `route` covers ONE task family. |

## Gap (Prompt requirement 2)

No single consolidated **routing diagnostics** surface: the operator could route one family at a time
but had no sweep across ALL families showing selected profile, candidate model chain, probe status,
fallback reason, fail-closed reason, and an output safety category in one place.

## Decision (surgical)

Add `model_diagnostics.py` (`build_routing_diagnostics` + `render_routing_diagnostics_markdown` +
`TASK_SAFETY_CATEGORY`) composing the existing `route_task_family` decision across every routed task
family, plus a `local-model diagnostics` CLI verb (JSON/Markdown). Reuses the existing eval harness
(`run_model_eval`) and the hash-only receipt table for the eval/no-raw proofs. No config change, no
schema change, no new model route, no cloud.
