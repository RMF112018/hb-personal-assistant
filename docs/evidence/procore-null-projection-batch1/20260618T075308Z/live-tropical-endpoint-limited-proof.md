# Procore Null Projection Batch 1 Live Tropical Endpoint-Limited Proof

Timestamp: 20260618T075308Z

Implementation commit: ffa28cb8b1065b800d4ef6b5edceaaa1a7bb5c1f
Branch: codex/procore-null-projection-batch1
Base: 9f62754f98ee12505a4ee403ae5cafb27bc972af
DB path: /Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite

## Status

NOT_ACCEPTED for the requested live count-delta target.

The endpoint-limited Tropical live proof ran successfully for only `punch-items` and `prime-contracts`, and endpoint-specific local replay ran successfully for only those two endpoints. However, the three requested target columns did not increase because the current Tropical live payload slice has zero non-nullish source values for those keys.

## Commands Run

CLI syntax verification:

```bash
env PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant procore live --help
env PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant procore live sync --help
env PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant procore analytics projection-reprocess --help
```

Live endpoint proof:

```bash
env HB_PROCORE_LIVE=1 PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant procore live sync --project tropical --endpoint punch-items --apply --sqlite-only --confirm-live-get --json
env HB_PROCORE_LIVE=1 PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant procore live sync --project tropical --endpoint prime-contracts --apply --sqlite-only --confirm-live-get --json
```

Endpoint-specific local replay:

```bash
env PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant procore analytics projection-reprocess --db "/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite" --project-key tropical --endpoint punch-items --apply --json
env PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant procore analytics projection-reprocess --db "/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite" --project-key tropical --endpoint prime-contracts --apply --json
```

## Live Receipts Summary

| Endpoint | State | Request count | Retrieved | Raw rows written | Structured rows written | Raw body emitted |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| punch-items | success | 1 | 4 | 4 | 4 | false |
| prime-contracts | success | 1 | 1 | 1 | 1 | false |

## Replay Receipts Summary

| Endpoint | Mode | Raw rows inspected | Primary rows written | Child rows written | Live Procore calls | External writeback |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| punch-items | apply | 4 | 4 | 12 | 0 | 0 |
| prime-contracts | apply | 5 | 5 | 0 | 0 | 0 |

## Count Deltas

| Table | Column/count | Before | After live sync | After endpoint replay | Delta |
| --- | --- | ---: | ---: | ---: | ---: |
| procore_ep_punch_items | total rows | 23 | 23 | 23 | 0 |
| procore_ep_punch_items | closed_at non-null | 0 | 0 | 0 | 0 |
| procore_ep_punch_items | closed_by non-null | 0 | 0 | 0 | 0 |
| procore_ep_prime_contracts | total rows | 5 | 5 | 5 | 0 |
| procore_ep_prime_contracts | show_line_items_to_non_admins non-null | 0 | 0 | 0 | 0 |
| procore_ep_budget_detail_rows | row count | 2496 | 2496 | 2496 | 0 |
| procore_ep_budget_detail_row_cells | row count | 225131 | 225131 | 225131 | 0 |

Budget Detail row/cell counts remained unchanged and nonzero.

## Body-Free Source Path Counts

These counts inspect local raw payload JSON internally for key presence/nullishness and emit only counts and key names.

| Endpoint | JSON key | Payload rows inspected | Key present count | Non-nullish key count | Raw payload values emitted |
| --- | --- | ---: | ---: | ---: | --- |
| punch-items | closed_at | 4 | 4 | 0 | false |
| punch-items | closed_by | 4 | 4 | 0 | false |
| prime-contracts | show_line_items_to_non_admins | 5 | 5 | 0 | false |

## Guardrails

Scheduled refresh called: no

SourceRefreshOrchestrator called: no

Project key: tropical only

Endpoints: punch-items and prime-contracts only

Procore writeback: no

Budget Detail modified: no

Raw payload emitted: no

Live Procore calls: only the two approved endpoint GET sync commands

## Conclusion

The implementation/evidence commit is present and the endpoint-limited live proof was executed. The live data slice does not currently contain non-null source values for the three Batch 1 target fields, so the requested target-column count deltas could not be achieved in this run. No broad company_id remediation, Budget Detail remediation, scheduler run, all-endpoint refresh, non-Tropical project refresh, Procore writeback, or raw payload emission was performed.
