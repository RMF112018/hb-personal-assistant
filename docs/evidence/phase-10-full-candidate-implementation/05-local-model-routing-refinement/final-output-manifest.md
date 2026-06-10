# Final Output Manifest — Local Model Routing Refinement

## Intended operator-facing output

`second-brain local-model diagnostics`: one consolidated, raw-free view of local model routing across
all Phase 10 task families — selected profile, candidate model chain, availability/probe status,
fallback reason, fail-closed reason, and declared output safety category — plus an offline eval
summary. Deterministic, fail-closed, never cloud.

## Generated proof artifacts

| Artifact | Path | From | Safe? |
|---|---|---|---|
| Routing diagnostics (JSON) | `01-routing-diagnostics-final-output.json` | present-models probe | yes |
| Routing diagnostics (MD) | `02-routing-diagnostics-final-output.md` | present-models probe | yes |
| Eval summary | `03-eval-summary-final-output.json` | `run_model_eval` synthetic | yes |
| Model-unavailable proof | `04-model-unavailable-proof.md` | unreachable + missing probes | yes |
| Schema-failure proof | `05-schema-failure-proof.md` | eval metrics + tests | yes |
| No-cloud-fallback proof | `06-no-cloud-fallback-proof.txt` | 3 probes + guardrail | yes |
| No-raw-persistence proof | `07-no-raw-persistence-proof.txt` | receipts-table introspection | yes |
| Safety scan | `08-safety-scan-results.txt` | scan | yes (0 findings) |
| Production DB unchanged | `09-production-db-unchanged-proof.txt` | sha256 | yes (unchanged) |

## Manual verification command

```bash
hb-assistant second-brain local-model diagnostics --no-json            # Markdown sweep
hb-assistant second-brain local-model diagnostics --mock --json        # offline shape
hb-assistant second-brain local-model eval --suite daily-brief --synthetic --json
```
