# Direct Procore Live Sync Eligibility Proof

Timestamp: 20260618T083033Z

Branch: codex/procore-null-projection-batch1

Batch 1 implementation commit: ffa28cb8b1065b800d4ef6b5edceaaa1a7bb5c1f

Tropical proof commit: da4069d2aea056159c5e264acfba9213cd00ea42

Caretta replay proof commit: ab8ba814704ee6a0e290b87c87dc7bf62d419d97

Live eligibility implementation commit: 197a961de396cfdc1f86a8f6152459bc2a18f4a3

## Scope

This proof covers direct endpoint-limited live sync eligibility only.

Project used for positive proof: caretta

Endpoints used for positive proof: prime-contracts, punch-items

Endpoint used for negative proof: budget-details

No scheduler, SourceRefreshOrchestrator, all-endpoint refresh, all-project refresh, Budget Detail refresh/reconciliation, Procore writeback, raw payload output, or push was used.

## Mapping Drift

Before the implementation proof, direct live sync reported `project_not_mapped` for caretta because the configured project seed lacked caretta/rybovich rows even though checked-in tests and local raw-payload DB evidence both referenced these mappings.

Corroborating local DB counts, body-free:

| Project | Procore project ID | Raw payload rows |
| --- | --- | ---: |
| caretta | 2145250 | 4936 |
| rybovich | 3133242 | 1429 |

The implementation commit adds the corroborated project mappings to the Procore project seed files and keeps scheduler policy unchanged.

## Validation

Passed:

```bash
env PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/python3.12 -m compileall src/hb_assistant/procore src/hb_assistant/source_refresh tests
env PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/ruff check src/hb_assistant/procore/live_gate.py src/hb_assistant/procore/live_sync.py src/hb_assistant/procore/__init__.py tests/test_procore_live_gate.py tests/test_procore_endpoint_audit.py tests/test_launcher_scheduler.py
env PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/python3.12 -m pytest tests/test_procore_endpoint_structured_projection_remediation.py tests/test_procore_null_projection_audit.py -q
env PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/python3.12 -m pytest tests/test_procore_live_gate.py -q
env PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/python3.12 -m pytest tests/test_sources_refresh.py -q
env PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/python3.12 -m pytest tests/test_procore_endpoint_audit.py::test_seed_projects_include_rybovich_and_caretta tests/test_launcher_scheduler.py::test_production_all_mapped_scope_selects_new_procore_projects tests/test_procore_live_gate.py -q
env PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant procore analytics projection-schema-audit --json
env PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant procore analytics projection-audit --endpoint punch-items --json
env PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant procore analytics projection-audit --endpoint prime-contracts --json
```

Broad Ruff note:

```bash
env PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/ruff check src/hb_assistant/procore src/hb_assistant/source_refresh tests
```

This broad command still reports unrelated pre-existing issues in non-Procore test files. Touched files pass Ruff.

## Positive Proof

Command:

```bash
env HB_PROCORE_LIVE=1 PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant procore live sync --project caretta --endpoint prime-contracts --apply --sqlite-only --confirm-live-get --json
```

Result:

| Field | Value |
| --- | --- |
| state | success |
| status | success |
| reason_codes | [] |
| request_count | 1 |
| retrieved_count | 1 |
| raw_payload_rows_written | 1 |
| structured_rows_written | 1 |
| project_eligibility | ok |
| endpoint_eligibility | ok |
| operator_live_authorization | ok |
| transport_attempted | true |
| raw_payload_body_emitted_to_stdout | false |

Command:

```bash
env HB_PROCORE_LIVE=1 PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant procore live sync --project caretta --endpoint punch-items --apply --sqlite-only --confirm-live-get --json
```

Result:

| Field | Value |
| --- | --- |
| state | success |
| status | success |
| reason_codes | [] |
| request_count | 1 |
| retrieved_count | 0 |
| raw_payload_rows_written | 0 |
| structured_rows_written | 0 |
| project_eligibility | ok |
| endpoint_eligibility | ok |
| operator_live_authorization | ok |
| transport_attempted | true |
| raw_payload_body_emitted_to_stdout | false |

`mapping_not_live_eligible` was eliminated for both mapped-project direct endpoint-limited commands.

## Negative Proof

Command:

```bash
env HB_PROCORE_LIVE=1 PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant procore live sync --project caretta --endpoint budget-details --apply --sqlite-only --confirm-live-get --json
```

Result:

| Field | Value |
| --- | --- |
| state | not_live_verified |
| status | fail_closed |
| reason_codes | endpoint_not_live_eligible; endpoint_unverified_for_live; phase05_unresolved_path_fail_closed_prompt00-3.2 |
| request_count | 0 |
| project_eligibility | ok |
| endpoint_eligibility | failed |
| operator_live_authorization | ok |
| transport_attempted | false |
| no_live_call_performed | true |
| raw_payload_body_emitted_to_stdout | false |

The unresolved `budget-details` endpoint remains blocked before transport.

## Guardrails

Scheduled refresh called: no

SourceRefreshOrchestrator called: no

All-endpoint refresh called: no

All-project refresh called: no

Budget Detail refresh/reconciliation modified: no

Procore writeback: no

Raw payload bodies or sensitive values emitted: no

Push performed: no
