# Phase 06B — Prompt 08: Overdue & Action Queue Model

**Status:** COMPLETE.
**Run date:** 2026-05-30
**Parent HEAD at start:** `3c72e91` (`phase-06b prompt-07: freshness & stale data reporting`)
**Objective:** A single operational queue of overdue/open work across Procore controls,
financials, schedule, safety/quality, and review-required signals — surfaced via
`procore live overdue --project KEY --json`. Read-only over local SQLite; no live access; no
raw values; no determinations.

---

## 1. What was built

- `src/hb_assistant/store/procore_action_queue.py` — `build_overdue_queue(project_key, *,
  now_utc, importance=None, endpoint_id=None, dimension=None, max_items=50, db_path=None)`.
  Deterministic, read-only. Reuses `procore_enrichment.get_procore_action_signals` and the
  Prompt 06 helpers `_dimensions_for` / `_parse_iso` from `procore_project_health`.
- CLI `procore live overdue --project KEY [--importance I] [--endpoint E] [--dimension D]
  [--max-items N] --json` (mirrors `procore live actions` / `project-health`).

### Per-row fields (each open action item)
`signal_type`, `endpoint_id`, `record_key`, `due_at_utc`, `status`
(`overdue` / `upcoming` / `no_due_date`), `days_overdue`, `importance`, `owner_entity_key`
(owner/responsible-party), `review_required` (review flag), `reason_codes`, `dimensions`,
`title_redacted`, `source_url_redacted`, `exposure_present`, `exposure_amount_names` (NAMES
only), `exposure_fact_count`.

### Inputs
- **open signals** (`procore_action_signals`, `signal_status='open'`) — the queue spine.
- **due dates** — signal `due_at_utc` first; canonical-record fallback (`procore_live_records.
  canonical_json_redacted`, `_DUE_DATE_FIELDS` allowlist) only re-emits the normalized ISO date.
- **review flag + source link** — joined from `procore_live_records` on `record_key`.
- **exposure rows** — `procore_financial_amount_facts` joined on `record_key` (names/counts only).

### Ordering & summary
Deterministic order: overdue-first → most-overdue → importance → due date → record_key →
signal_type. `summary` carries total_open / overdue / upcoming / no_due_date / high_importance /
review_required / by_dimension.

---

## 2. Repo-truth / stop-condition reconciliation

- **Due dates ARE normalizable** for the key path: action signals already carry a normalized
  `due_at_utc` at emission time; the read model uses that as the authoritative source and only
  falls back to a conservative canonical-record allowlist when the signal is silent. No
  endpoint-specific due-date heuristics were invented.
- **Stop condition handled, not hit:** the prompt says to stop if due dates cannot be normalized
  safely and to document unsupported endpoint-specific due-date logic. Rather than failing, the
  output exposes `unsupported_due_date_endpoints` — every endpoint for which no queued item
  produced a normalizable due date — so unsupported due-date logic is reported explicitly per run.
- **Read-only, no persistence:** consistent with Prompts 06/07 (and the dry-run-default
  guardrail), no table/migration was added — the queue is derived on demand. Schema is V19.

---

## 3. Due-date normalization & unsupported endpoints

Due date is taken from the signal's normalized `due_at_utc`; when absent, `build_overdue_queue`
reads one normalized date from the canonical record via the `_DUE_DATE_FIELDS` allowlist
(`due_date`, `due_at`, `due_at_utc`, `due`, `deadline`, `expected_response_at`,
`expected_delivery_date`, `required_on_site_date`) and re-emits **only** the parsed ISO value.
Any endpoint whose queued items all lack a normalizable due date is listed in
`unsupported_due_date_endpoints` (in the proof fixture: `commitments`, `observations`).

---

## 4. Proof (08-overdue-and-action-queue-proof.json)

Seeded a temp DB (isolated `HB_PA_CONFIG`) with a 6-signal synthetic fixture — an explicitly
overdue high RFI signal (with owner key), a no-signal-due RFI that falls back to the canonical
record due date, a review-required safety observation, a high cost-exposure commitment (with an
amount fact), a future-due delivery, and one resolved signal (excluded) — and dumped
`build_overdue_queue`:

```
summary: total_open 5, overdue 2, upcoming 1, no_due_date 2, high_importance 3, review_required 1
unsupported_due_date_endpoints: ["commitments", "observations"]
```

See [`08-overdue-and-action-queue-proof.json`](./08-overdue-and-action-queue-proof.json).

---

## 5. Validation (no live calls)

| Command | Exit | Result |
| --- | --- | --- |
| `pytest tests/test_procore_action_queue.py` | 0 | 14 passed (status/filters/joins/exposure/ordering/no-leak/CLI) |
| `pytest -m "not live" tests/test_procore*.py` | 0 | no regression (+14) |
| `ruff check .` | 0 | All checks passed |
| `mypy src` | 0 | Success: no issues found |
| `hb-assistant procore validate --json` | 0 | ok, 28/28 |
| `hb-assistant procore live overdue --project tropical --json` | 0 | ok envelope |

---

## 6. Guardrail attestations

- **No live Procore call** (`no_live_call_performed: true`); **no writeback**; **read-only**
  (no migration, no persistence).
- **No raw bodies, tokens, signed URLs, or PEMs** — only signal/record metadata, normalized
  due dates, redacted titles, source-link strings, and exposure NAMES. Amount **values** are
  never emitted. Proof JSON secret/raw-value scanned (0 findings).
- **No legal/claims/financial/safety/entitlement/schedule-impact determination**
  (`determinations_made: false`) — the queue is an intelligence/review aid; `status` and
  `reason_codes` are deterministic labels, not decisions.
