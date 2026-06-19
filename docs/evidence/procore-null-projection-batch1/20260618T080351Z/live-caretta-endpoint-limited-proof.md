# Procore Null Projection Batch 1 Caretta Endpoint-Limited Proof

Timestamp: 20260618T080351Z

Branch: codex/procore-null-projection-batch1

Implementation commit: ffa28cb8b1065b800d4ef6b5edceaaa1a7bb5c1f

Tropical proof commit: da4069d2aea056159c5e264acfba9213cd00ea42

Tropical proof status: NOT_ACCEPTED because Tropical live payloads had zero non-nullish source values for the three Batch 1 target keys.

Caretta proof status: ACCEPTED

## Scope

Project used in this new proof: caretta only

Endpoints used in this new proof: punch-items and prime-contracts only

No scheduler, SourceRefreshOrchestrator, all-endpoint refresh, all-mapped project scope, Tropical retry, Rybovich run, Budget Detail refresh/reconciliation, schema migration, Procore writeback, or raw payload output was used.

## Before Counts

| Table | Metric | Count |
| --- | --- | ---: |
| procore_ep_punch_items | caretta rows | 0 |
| procore_ep_punch_items | closed_at non-null | 0 |
| procore_ep_punch_items | closed_by non-null | 0 |
| procore_ep_prime_contracts | caretta rows | 0 |
| procore_ep_prime_contracts | show_line_items_to_non_admins non-null | 0 |
| procore_ep_budget_detail_rows | rows | 2496 |
| procore_ep_budget_detail_row_cells | rows | 225131 |

## Live CLI Verification

The direct endpoint-limited CLI surface was verified before live commands:

```bash
env PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant procore live --help
env PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant procore live sync --help
env PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant procore analytics projection-reprocess --help
```

## Direct Live Commands

```bash
env HB_PROCORE_LIVE=1 PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant procore live sync --project caretta --endpoint punch-items --apply --sqlite-only --confirm-live-get --json
env HB_PROCORE_LIVE=1 PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant procore live sync --project caretta --endpoint prime-contracts --apply --sqlite-only --confirm-live-get --json
```

Both direct live commands failed closed before transport with `state=gate_blocked`, `reason_codes=["mapping_not_live_eligible"]`, `request_count=0`, and `no_live_call_performed=true`. No Procore GET was performed by these two commands.

## Endpoint-Specific Local Replay

Because the direct live commands did not populate the Batch 1 fields, endpoint-specific local replay was run only for caretta and only for the two Batch 1 endpoints:

```bash
env PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant procore analytics projection-reprocess --db "/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite" --project-key caretta --endpoint punch-items --apply --json
env PYTHONPATH=src /Users/bobbyfetting/hb-personal-assistant/.venv/bin/hb-assistant procore analytics projection-reprocess --db "/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite" --project-key caretta --endpoint prime-contracts --apply --json
```

| Endpoint | Raw full rows inspected | Primary rows written | Child rows written | Live Procore calls | External writeback |
| --- | ---: | ---: | ---: | ---: | ---: |
| punch-items | 0 | 0 | 0 | 0 | 0 |
| prime-contracts | 1 | 1 | 0 | 0 | 0 |

## After Counts

| Table | Metric | Before | After | Delta |
| --- | --- | ---: | ---: | ---: |
| procore_ep_punch_items | caretta rows | 0 | 0 | 0 |
| procore_ep_punch_items | closed_at non-null | 0 | 0 | 0 |
| procore_ep_punch_items | closed_by non-null | 0 | 0 | 0 |
| procore_ep_prime_contracts | caretta rows | 0 | 1 | 1 |
| procore_ep_prime_contracts | show_line_items_to_non_admins non-null | 0 | 1 | 1 |
| procore_ep_budget_detail_rows | rows | 2496 | 2496 | 0 |
| procore_ep_budget_detail_row_cells | rows | 225131 | 225131 | 0 |

Acceptance target met: `procore_ep_prime_contracts.show_line_items_to_non_admins` increased to nonzero.

Budget Detail row count remained unchanged and nonzero.

Budget Detail row-cell count remained unchanged and nonzero.

## Body-Free Attestation

This evidence reports command names, endpoint names, row counts, status codes, reason-code names, and aggregate replay counts only. It does not emit raw payload bodies, payload fragments, business-sensitive values, comments, descriptions, notes, credentials, signed URLs, or full emails.

No push performed.
