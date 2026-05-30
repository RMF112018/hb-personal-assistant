# Phase 06B — Prompt 07: Freshness & Stale Data Reporting

**Status:** COMPLETE.
**Run date:** 2026-05-30
**Parent HEAD at start:** `50a7c6d` (`phase-06b prompt-06: project health read model`)
**Objective:** Endpoint/project freshness reporting so the user knows whether data is current
enough to trust — surfaced via `procore live stale --project KEY --json`. Read-only over local
SQLite; no live access; no raw values; no determinations.

---

## 1. What was built

- `src/hb_assistant/store/procore_freshness.py` — `build_freshness_report(project_key, *, now_utc,
  stale_days=7, db_path=None)`. Deterministic, read-only (reuses `get_connection`).
- CLI `procore live stale --project KEY [--stale-days N] --json` (mirrors `procore live project-health`).

### Statuses (per registry endpoint, 59 total)
| Status | Meaning |
| --- | --- |
| `current` | freshness age ≤ `stale_days` |
| `stale` | freshness age > `stale_days` |
| `never_synced` | operational endpoint with no watermark / run / record |
| `unknown` | signal row exists but no usable timestamp and no records |
| `fail_closed` | held (`live_verified=False`) endpoint — excluded from operational tally + stale list |

### Freshness source priority (all written only on a successful sync)
`procore_live_sync_watermarks.last_success_at_utc` → latest successful
`procore_live_sync_runs.completed_at_utc` (state success/partial_success) → max
`procore_live_records.last_seen_at_utc` → none. The chosen source is reported per endpoint (`source`).

### Recommended sync commands
For `stale` + `never_synced` **operational** endpoints only, a string (never executed):
`HB_PROCORE_LIVE=1 hb-assistant procore live sync --project {p} --endpoint {id} --apply
--sqlite-only --max-pages 3 --max-items 100 --confirm-live-get --json`.

---

## 2. Repo-truth / stop-condition reconciliation

- **Freshness IS computable** from the existing schema (watermarks + sync runs + record timestamps) —
  the stop condition ("schema differs; adapt and document") is not triggered; the adaptation is using
  the watermark `last_success_at_utc` (written only on success) as the authoritative per-endpoint
  signal, with sync-run and record-recency fallbacks. Documented in
  `docs/architecture/17-procore-operational-intelligence-phase-06b.md`.
- **Read-only, no persistence:** persistence to `procore_endpoint_freshness` was explicitly optional
  ("if schema migration is part of this prompt"). Per the dry-run-default guardrail + simplicity +
  consistency with the Prompt 06 read model, no table/migration was added — freshness is derived on
  demand. A snapshot table is a documented deferred option (no trend-history need today).

---

## 3. Fail-closed exclusion (validation requirement)

The 3 held endpoints (`purchase-order-detail-line-items`, `budget-change-line-items`,
`budget-details`) are reported with status `fail_closed`, are **absent** from `stale_endpoints`,
carry **no** recommended sync command, and are **excluded** from `summary.operational_total`.
Proven by `test_fail_closed_endpoints_are_not_stale_operational`.

---

## 4. Proof (07-freshness-and-stale-data-proof.json)

Seeded a temp DB (rfis current watermark, submittals old watermark, meetings NULL watermark, rest
untouched) and dumped `build_freshness_report` (per-endpoint list trimmed to a representative sample
for readability; summary is over all 59):

```
summary: current 1, stale 1, never_synced 53, fail_closed 3, unknown 1, operational_total 56
```

See [`07-freshness-and-stale-data-proof.json`](./07-freshness-and-stale-data-proof.json).

---

## 5. Validation (no live calls)

| Command | Exit | Result |
| --- | --- | --- |
| `pytest tests/test_procore_freshness.py` | 0 | 5 passed (each status, fail-closed exclusion, recommended commands, CLI shape, no-leak) |
| `pytest -m "not live" tests/test_procore*.py` | 0 | 757 passed, 1 deselected (no regression; +5) |
| `ruff check store/procore_freshness.py cli/procore.py` | 0 | All checks passed |
| `mypy src` | 0 | Success: no issues in 143 source files |
| `hb-assistant procore validate --json` | 0 | ok, 28/28 |

---

## 6. Guardrail attestations

- **No live Procore call** (`no_live_call_performed: true`); **no writeback**; **read-only**
  (no migration, no persistence).
- **No raw bodies, tokens, signed URLs, or PEMs** — only statuses / counts / timestamps /
  endpoint ids / recommended-command strings. Proof JSON secret/raw-value scanned (0 findings);
  the `HB_PROCORE_LIVE=1` in recommended commands is a documented operator env flag, not a secret.
- **No legal/claims/financial/safety/entitlement/schedule-impact determination**
  (`determinations_made: false`).
- **Held endpoints never recommended for sync and never counted as operational stale.**
