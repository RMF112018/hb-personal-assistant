# Synthetic Eval Labeling Proof

`local-model eval` now labels the run mode unambiguously so a synthetic run is never mistaken for live
model-quality proof.

| Invocation | `mode` | `eval_mode` |
| --- | --- | --- |
| `eval --suite daily-brief --synthetic` | `synthetic` | `synthetic_offline_contract` |
| `eval ... --live` | `live` | `live_local_model` |

Synthetic mode replays canned fixtures and proves the **harness/schema contract** (JSON-valid,
schema-valid, redaction-pass), not live model differentiation (in synthetic mode all profiles replay
identical output). Live model quality is a separate artifact — see `live-model-performance-proof.md`.

Live observation: `eval --suite daily-brief --synthetic --json` → `ok=true`, `dry_run=true`,
`eval_mode=synthetic_offline_contract`, json/schema/redaction rates 1.0.

Unit coverage: `tests/test_local_model_routing_cli.py::test_eval_synthetic_json_shape_and_exit_0`
asserts `eval_mode == "synthetic_offline_contract"`.
