# Daily Log Selection Scope Proof — Phase 04 Prompt 08

**Date:** 2026-05-28
**Branch:** `main`
**Prompt:** Phase 04 Prompt 08 — Daily Log Selection Scope and Dry-Run
**Prior commits:** `01d0d19` (RFI), `1ca4a43` (Submittal), `400a704` (Observation), `3a670e1` (Meeting)

## Scope summary

Procore's `list-daily-logs` endpoint returns one daily log per project per
date, each carrying multiple parallel sub-collections. The Phase 04 Prompt 08
selection scope at
`resources/config/procore_daily_log_selection.seed.yaml` partitions those
sub-collections into three buckets:

- **Selected sections** persist as canonical rows with a declared
  `canonical_field_keys` whitelist and `review_required=False`. These are
  the per-section signals operators rely on (counts, weather, manpower,
  DCR, delivery).
- **Review-only sections** (`notes`) persist with `review_required=True`
  and a `daily_log_review_only_section` routing reason; body text is
  reduced to a SHA-256 hash-only summary. Notes never bypass review.
- **Routed-to-review sections** (`accident`, `injury`, `delay`, `safety`)
  persist with `review_required=True` AND `safety_route=True`; body text
  is reduced to a SHA-256 hash-only summary. Accident / injury / delay /
  safety text never enters normal canonical rows by construction.

The endpoint itself is already `verification_status: official_docs_verified`
and `is_live_eligible: true` in the active contract (lines 95-106 of
`resources/config/procore_endpoint_contract.seed.yaml`) — no contract
changes were needed in this prompt. The selection scope governs how the
apply path persists records once live execution returns daily log payloads.

## Selected sections

| id       | payload_key      | category              | canonical_field_keys |
|----------|------------------|-----------------------|----------------------|
| counts   | `counts`         | `daily_log_counts`    | id, count, trade, work_area, log_date, created_at, updated_at |
| weather  | `weather_logs`   | `daily_log_weather`   | id, temperature, conditions, wind_speed, humidity, observed_at, log_date, created_at, updated_at |
| manpower | `manpower_logs`  | `daily_log_manpower`  | id, company, headcount, hours, trade, log_date, created_at, updated_at |
| dcr      | `dcr_logs`       | `daily_log_dcr`       | id, status, log_date, created_at, updated_at, author_id |
| delivery | `delivery_logs`  | `daily_log_delivery`  | id, vendor, item_description, quantity, received_at, log_date, created_at, updated_at |

Each canonical row also carries `parent_daily_log_stable_key` linking back to
the parent daily log.

## Review-only sections

| id     | payload_key   | category              | treatment |
|--------|---------------|-----------------------|-----------|
| notes  | `notes_logs`  | `daily_log_notes`     | `review_required=True`, `routing_reason="daily_log_review_only_section"`, body text reduced to SHA-256 hash-only `body_summary`; canonical_fields restricted to id + timestamps. |

## Routed-to-review sections

| id       | payload_key             | category                       | routing reason |
|----------|-------------------------|--------------------------------|----------------|
| accident | `accident_logs`         | `daily_log_accident_review`    | `daily_log_routed_to_review:accident` |
| injury   | `injury_logs`           | `daily_log_injury_review`      | `daily_log_routed_to_review:injury` |
| delay    | `delay_logs`            | `daily_log_delay_review`       | `daily_log_routed_to_review:delay` |
| safety   | `safety_violation_logs` | `daily_log_safety_review`      | `daily_log_routed_to_review:safety` |

All routed-to-review rows carry `review_required=True`, `safety_route=True`,
SHA-256 hash-only `body_summary`, and minimal canonical_fields (id +
timestamps + `parent_daily_log_stable_key`).

## Fixture-derived row counts

Running the normalizer on `DAILY_LOG_SAMPLE_PAYLOAD`
(`src/hb_assistant/construction/fixtures/procore.py`) yields the following
per-category row counts:

| category                       | rows |
|--------------------------------|------|
| `daily_log_counts`             | 3    |
| `daily_log_weather`            | 2    |
| `daily_log_manpower`           | 3    |
| `daily_log_dcr`                | 2    |
| `daily_log_delivery`           | 2    |
| `daily_log_notes`              | 2    |
| `daily_log_accident_review`    | 1    |
| `daily_log_injury_review`      | 1    |
| `daily_log_delay_review`       | 1    |
| `daily_log_safety_review`      | 1    |

Totals: **18 rows** across all sections; **6 rows** flagged
`review_required=True` (notes ×2 + accident + injury + delay + safety);
**4 rows** flagged `safety_route=True` (accident + injury + delay + safety).

## Stop-condition attestation

The prompt names three stop conditions; each is structurally satisfied by
the selection-scope and normalizer design:

| Stop condition | Structural defense |
|----------------|--------------------|
| Broad daily logs sync persists all sections | The normalizer only emits records for section arrays declared in the selection scope; unknown / undeclared section keys are silently ignored. There is no "persist everything" path. |
| Accident / injury / delay text enters normal rows | Routed-to-review sections live exclusively in the `routed_to_review_sections` bucket. Their bucket treatment forces `review_required=True` + `safety_route=True` + hash-only `body_summary`. The bucket assignment is structural — not derived from row content — so reclassifying a section to a different bucket would require editing the seed YAML. |
| Notes logs bypass review | `notes_logs` lives exclusively in `review_only_sections`. Its bucket treatment forces `review_required=True` + hash-only `body_summary` regardless of payload content. |

## Guardrails

- **Read-only** external Procore HTTP surface (GET-only by construction).
- **No writeback** to Procore.
- **No raw body text persisted** — every review-only and routed-to-review
  section row carries only a SHA-256 hash-only `body_summary`.
- **Accident / injury / delay / safety always review_required** + always
  `safety_route=True` (structural, not heuristic).
- **Notes always review_required** + hash-only body summary.
- **Redaction applied** on every canonical row (`redaction_applied: True`).

## References

- Selection scope seed: `resources/config/procore_daily_log_selection.seed.yaml`
- Selection-scope loader + Pydantic model: `src/hb_assistant/procore/daily_log_selection.py`
- Normalizer module: `src/hb_assistant/procore/normalizers/daily_log.py`
- Synthetic fixture: `src/hb_assistant/construction/fixtures/procore.py` (`DAILY_LOG_SAMPLE_PAYLOAD`)
- Dispatch wiring + apply branch: `src/hb_assistant/procore/sync.py` (`DAILY_LOG_ENDPOINT_ID`, `NORMALIZER_DISPATCH`)
- Validate check: `src/hb_assistant/procore/validate.py` (`daily_log_selection_and_dispatch_present`)
- Test suite: `tests/test_procore_daily_log_selection.py`, `tests/test_procore_daily_log_normalizer.py`, `tests/test_procore_cli_sync_daily_log_dry_run.py`, `tests/test_procore_daily_log_sqlite_idempotency.py`
- Active contract entry: `resources/config/procore_endpoint_contract.seed.yaml` lines 95-106 (`list-daily-logs`)

## Verification matrix

| Gate | Result |
|------|--------|
| `python -m pytest -q --no-header` | 816 passed, 1 skipped (live OAuth) |
| `ruff check .` | clean |
| `mypy .` | clean |
| `python -m compileall src tests` | clean |
| `hb-assistant procore validate --json` | 24 checks, 23 pass, 1 informational (`mapping_consistent` pre-existing) |
| `hb-assistant procore sync run --endpoints list-daily-logs --dry-run --json` | one per_endpoint entry with `live_eligible: true`, `verification_status: official_docs_verified`, `would_persist_sections_separately: true` |
| Boundary regression (sensitive-scan / offline-enforcement / client-secret isolation) | green |
