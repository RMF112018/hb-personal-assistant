# 22 — Final Summary (Phase 10 V52/V53 Daily-Brief Effectiveness Telemetry, pre-merge patched)

## Outcome

Additive, deterministic, raw-safe, **observational** daily-brief effectiveness / ranking-policy
telemetry layer (schema **V52** + **V53** reconcile) on top of the V51 ranking/assembly overlay. Reads
V50/V51 metadata and persists only raw-free counts/scores/hashes/reason codes to six guarded tables.
No V50/V51 behavior changed; nothing external written.

## Pre-merge patch of commit 526e01a1

1. **`--apply` safety:** rejected (exit 2) without an explicit `--db`, and the `--db` must resolve
   under an OS temp root unless `--allow-non-tmp-db` is passed — checked **before** the store is opened
   so a rejected call never migrates anything. Cannot persist against the prod app DB by accident.
2. **Post-exposure outcome attribution:** only a disposition event at/after the exposure-proxy time is
   attributed (lag never negative); a pre-exposure disposition is excluded with
   `status_reason=pre_existing_disposition_not_attributed` (never converted to ignored/stale);
   `ignored` only for genuinely open, actionable items aged past the lag window.
3. **Multi-brief eval:** rank-position maps keyed by `(ranking_run_id, candidate_id)`;
   `ranking_policy_eval_items` gains `ranking_run_id` + composite PK so a candidate surfaced in two
   ranking runs keeps a distinct fact per run. Shipped as **V53** because prod was externally migrated
   to the original V52 shape (see below); the reconcile is a non-destructive, idempotent rebuild.
4. **Report policy-version** now rendered correctly.

## Validation summary

| Gate | Result |
|---|---|
| compile | pass (`21-compile.txt`) |
| ruff (changeset) | pass (`19-ruff.txt`) |
| mypy `src` | V52/V53 clean; only 2 pre-existing `review_burden_mart.py` errors (`20-mypy.txt`) |
| focused pytest (9 files) | 62 passed (`18-pytest-focused.txt`) |
| V50/V51 + schema + inventory regression | pass |
| no-raw-leak scan (evidence dir) | `ok: true`, 0 categories (`15-no-raw-leak-scan.json`) |
| guard columns zero | guard_sum_total 0 after apply (`16-…`) |
| multi-run facts preserved | 2 eval-item rows for the shared candidate (`16-…`) |
| dry-run zero rows | confirmed (`04`/`05`) |
| apply requires `--max-persist` + temp `--db`; total-projected cap fails closed | CLI exit 2 / exit 3 tests |
| apply does not mutate V50/V51 tables | before/after content-fingerprint test |
| production DB SHA-256 unchanged | `a403b67b…` before == after (`17-prod-db-sha-unchanged.txt`) |

## DB-copy validation + prod-state note

The plain prod DB was copied to `/tmp`; the copy presented at head **52 with the original
`ranking_policy_eval_items` shape** (no `ranking_run_id`) — i.e., an **external editable-install runner
migrated prod to V52 between sessions** with the pre-patch DDL. Opening the copy ran the migrator,
which **reconciled it to V53** (added `ranking_run_id`, rebuilt the PK) and then ran
`evaluate-effectiveness` cleanly (`no_ranked_briefs`, the honest result for a copy with no V51 ranking
data; zero writes). Guard sums 0, SQL-visible URL/email/token hits 0, prod SHA-256 identical before and
after. This patch's operations touched only the `/tmp` copy.

## Deferred (not resolved here)

Table-lifecycle governance classification of the V49–V53 telemetry tables in
`table_lifecycle_status_contract.json` remains pre-existing governance debt (the
`*_tables_classified_in_lifecycle_contract` / `second_brain_no_writeback_proof` tests were already red
at the V51 HEAD `6938380b`); a separate governance PR owns it.
