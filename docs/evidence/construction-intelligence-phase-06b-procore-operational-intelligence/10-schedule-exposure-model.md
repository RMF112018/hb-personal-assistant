# Phase 06B — Prompt 10: Schedule Exposure Model

**Status:** COMPLETE.
**Run date:** 2026-05-31
**Parent HEAD at start:** `3900ce2` (`phase-06b prompt-09: cost exposure model`)
**Objective:** Join the schedule-bearing Procore domains (RFIs, submittals, schedule activities,
meetings, punch, observations, inspections) into a schedule exposure model — surfaced as
`procore live schedule exposure --project KEY --json`. Advisory/review aid only; read-only over
local SQLite; no live access; no raw values; **no delay/entitlement/responsibility determinations**.

---

## 1. What was built

- `src/hb_assistant/store/procore_schedule_exposure.py` — `build_schedule_exposure(project_key, *,
  now_utc, exposure_category=None, importance=None, max_items=50, db_path=None)`. Deterministic,
  read-only. Reuses `get_procore_action_signals` (`procore_enrichment`),
  `_dimensions_for` / `_parse_iso` (`procore_project_health`), and `_due_status` / `_canonical_due`
  / `_record_key` (`procore_action_queue`).
- CLI `procore live schedule exposure --project KEY [--type C] [--importance I] [--max-items N]
  --json` — a new `live schedule` sub-group under `live` (mirrors the `live financial exposure`
  verb).

### Exposure categories (the six the prompt specifies)
| Category | Source signals |
| --- | --- |
| `overdue_rfi` | `rfi_overdue` |
| `overdue_submittal` | `submittal_overdue` |
| `critical_or_low_float_activity` | `activity_critical`, `activity_zero_float`, `activity_constrained`, `activity_deadline_variance` |
| `meeting_action_topic` | `meeting_topic_open_high_priority` |
| `inspection_punch_blocking` | `inspection_overdue`, `inspection_has_deficient_items`, `inspection_has_unanswered_items`, `inspection_open_safety`, `punch_overdue`, `punch_due_tomorrow`, `punch_assignment_waiting`, `punch_unresolved_response`, `observation_open_safety`, `observation_high_priority` |
| `schedule_impact_flag` | `rfi_schedule_impact_flagged`, `submittal_required_on_site_date_near`, `purchase_order_delivery_due`, `observation_due_soon` |
| `daily_log_delay` | *(no signal source — see §2; always 0, listed under `unsupported_categories`)* |

### Per-item fields
`exposure_category`, `signal_type`, `endpoint_id`, `record_key`, `due_at_utc`, `status`
(`overdue` | `upcoming` | `no_due_date`), `days_overdue`, `importance`, `owner_entity_key`,
`review_required`, `reason_codes`, `dimensions`, `title_redacted`, `source_url_redacted`.

### Inputs
- **classification spine** — open `procore_action_signals` mapped via the explicit
  `_SCHEDULE_EXPOSURE_SIGNAL_MAP` (only schedule-bearing types; others skipped).
- **due dates** — the signal's normalized `due_at_utc` first, falling back to a normalized date
  extracted from the live record's `canonical_json_redacted` (never the raw field value).
- **source link + review flag** — `procore_live_records` joined by `record_key`.

---

## 2. Repo-truth / stop-condition reconciliation

- **Signals already encode the schedule semantics** — the projection layer (Phase 06A) emits the
  RFI/submittal/schedule/meeting/punch/observation/inspection signal vocabulary; Prompt 10
  classifies and enriches rather than re-deriving from raw payloads.
- **Daily logs have no signal source** — the package brief lists daily logs, but no daily-log
  projection emits action signals in this repo (repo truth wins over the brief). Rather than
  fabricate, `daily_log_delay` is a declared canonical category (always 0) echoed under
  `unsupported_categories` with a reason string — the same stop-condition surface style as the
  overdue model's `unsupported_due_date_endpoints`.
- **Stop condition honored** — "stop if implementation would make claims/delay determinations
  rather than exposure signals." The model emits only counts, category labels, reason codes, due
  status, and source refs; it never asserts who caused a delay, how many days are owed, or that a
  deadline was breached. A no-determination word scan guards the output. Advisory/review only.
- **Read-only, no persistence** — consistent with Prompts 06–09 and the dry-run-default guardrail;
  no table/migration was added (schema stays V19). Exposure is derived on demand.

---

## 3. Exposure classification & determination safety

- Classification is a literal `signal_type → exposure_category` table (auditable; no keyword
  guessing about *what* a signal is).
- **Due status is descriptive, not adjudicative** — `overdue`/`upcoming`/`no_due_date` +
  `days_overdue` describe the gap between `now` and a recorded due date; the model never attributes
  cause, fault, or entitlement, and never asserts a number of days *owed*.
- `review_required` = contributing signal `importance == "high"` OR `exposure_category` ∈
  {`overdue_rfi`, `overdue_submittal`, `critical_or_low_float_activity`,
  `inspection_punch_blocking`} OR the record's own `review_required` flag (documented triage label;
  carries reason codes `review_required_high_sensitivity` / `review_required_record`).

---

## 4. Proof (10-schedule-exposure-proof.json)

Seeded an isolated temp DB via `emit_action_signal` across all categories — an overdue RFI (with a
review-flagged live record + canonical-due fallback + redacted source link), an overdue submittal,
two critical/low-float activities, a high-priority meeting topic, an overdue inspection, an
upcoming + an overdue punch item, a high-priority observation, an RFI schedule-impact flag, a PO
delivery-due flag, and an unmapped cost signal (correctly excluded) — and dumped
`build_schedule_exposure`:

```
summary: total 11, review_required 9, overdue 4,
  by_category { overdue_rfi 1, overdue_submittal 1, critical_or_low_float_activity 2,
                meeting_action_topic 1, inspection_punch_blocking 4, schedule_impact_flag 2,
                daily_log_delay 0 },
  by_importance { high 4, medium 7, low 0 }
unsupported_categories: [ daily_log_delay ]
```

See [`10-schedule-exposure-proof.json`](./10-schedule-exposure-proof.json).

---

## 5. Validation (no live calls)

| Command | Exit | Result |
| --- | --- | --- |
| `pytest tests/test_procore_schedule_exposure.py` | 0 | 14 passed (each category / unmapped-skip / daily-log unsupported / overdue + upcoming status / review flags / canonical-due fallback / filters / ordering / no-determination / CLI) |
| `pytest -m "not live" tests/test_procore*.py` | 0 | no regression (+14) |
| `ruff check src/hb_assistant/cli/procore.py tests/test_procore_schedule_exposure.py` | 0 | All checks passed |
| `mypy src` | 0 | Success: no issues found in 143 source files |
| `hb-assistant procore validate --json` | 0 | ok, 28/28 |
| `hb-assistant procore live schedule exposure --project tropical --json` | 0 | ok envelope |

---

## 6. Guardrail attestations

- **No live Procore call** (`no_live_call_performed: true`); **no writeback**; **read-only**
  (no migration, no persistence).
- **No raw bodies, tokens, signed URLs, or PEMs** — only signal/record metadata, category labels,
  reason codes, redacted titles, and source-link strings. Proof JSON secret/raw-value scanned
  (0 findings).
- **No legal/claims/delay/entitlement/responsibility/schedule-impact determination**
  (`determinations_made: false`) — banned-determination-word scan over the content (0 findings).
