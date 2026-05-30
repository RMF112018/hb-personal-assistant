# Phase 06B — Prompt 05: Endpoint Coverage & Payload Contracts

**Status:** COMPLETE.
**Run date:** 2026-05-30
**Parent HEAD at start:** `5e41fc2` (`phase-06b prompt-04: held endpoint remediation & disposition`)
**Objective:** Current endpoint coverage reporting showing, per endpoint, what raw scalar fields are
captured, summarized (hash-only), intentionally omitted, or projected — as a coverage matrix by
endpoint family. **Names/types/counts only; never raw values.** No live Procore call; no writeback.

---

## 1. What was extended (existing read model)

The per-endpoint, payload-driven read model already existed (`procore/coverage.py::
compute_payload_coverage`, CLI `procore live coverage --raw-payload`). This prompt **hardened** it and
added a **by-family matrix**:

- `compute_payload_coverage` now additionally emits (additive — existing keys preserved):
  `normalizer_name`, `normalizer_version` (`NORMALIZATION_SCHEMA_VERSION`), and classifies the
  canonical output into `captured_scalar_fields`, `hash_only_fields` (the `*_summary`/`*_ref` redacted
  summaries, or `{hash_prefix,...}` value-shape), `projected_containers`
  (entities/edges/action_signals/text_intelligence), and `intentionally_omitted_fields` (raw fields
  not carried into the row — some still feed projections). All names only.
- `build_coverage_matrix(payloads_dir)` (CLI `procore live coverage-matrix [--payloads-dir]`)
  aggregates **by endpoint family**. Every endpoint emits a contract row: normalizer name/version,
  the documented `_FAMILY_PROJECTION` targets (entities / edges / action_signals / text_intelligence /
  financial tables), sensitivity, and held status. Endpoints with a local `<endpoint_id>.json` sample
  under `--payloads-dir` are enriched with the field-name buckets above (`payload_source: "fixture"`);
  the rest are `contract_only` (`payload_source: "none"`). Held endpoints with no normalizer (e.g.
  `budget-details`) report `registered: false`.

---

## 2. No-raw-values guarantee (stop condition)

The stop condition — *"persisting raw payload values to evidence"* — is **structurally prevented**:
the matrix output is field names, types, and counts only. `compute_payload_coverage` reports
`raw_field_paths` as `{path, type}` (no values) and bucket lists as field NAMES; `build_coverage_matrix`
copies only those names + counts. The evidence matrix and tests were scanned for the synthetic fixture
value markers (`SYNTH`, `example.test`, `SYNTHSIG`, free-text bodies) and secret patterns — **0
findings**. `no_raw_values_persisted: true` is asserted at both layers.

The synthetic fixtures (`tests/fixtures/procore_coverage/*.json`) are clearly-fake field-shape samples
(not raw Procore bodies); only their field NAMES surface in the matrix.

---

## 3. Coverage matrix (endpoint-coverage-matrix.json)

`procore live coverage-matrix --payloads-dir tests/fixtures/procore_coverage --json`:
**17 families, 59 endpoints, 5 fixture-sampled.** See
[`endpoint-coverage-matrix.json`](./endpoint-coverage-matrix.json).

### Financial endpoint — `commitment-line-items` (sensitivity high)
- `captured_scalar`: amount, unit_cost, quantity, extended_amount, total_amount, position, uom,
  extended_type, updated_at, wbs_code_id, wbs_flat_code, wbs_description, cost_code_id,
  line_item_type_id, tax_code_id, commitment_line_item_id, prime_line_item_id.
- `hash_only`: `description_summary` (free-text never captured raw).
- projection family targets include `procore_financial_amount_facts` + edges/signals.

### High-sensitivity PII endpoint — `punch-items` (sensitivity high, review_required_default true)
- `hash_only`: `description_summary`, `schedule_risk_reason_summary`, and the people refs
  `ball_in_court_summary`, `created_by_summary`, `closed_by_summary`, `assignees_summary`,
  `assignments_summary`, `punch_item_manager_summary`, `final_approver_summary`,
  `custom_fields_summary`. Raw `description` / `created_by` are **not** in `captured_scalar`.

### Enriched-family example — `daily-log-weather`
- `projected_containers`: entities, edges, action_signals (entity/edge/signal counts > 0);
  `intentionally_omitted` lists raw `created_by`/`vendor`/`location`/`attachments` (carried into
  projected entities/edges, not the scalar row).

---

## 4. Validation (no live calls)

| Command | Exit | Result |
| --- | --- | --- |
| `pytest tests/test_procore_coverage_matrix.py` | 0 | 9 passed (names-only, financial, high-sensitivity, by-family, drift guard, contract-only) |
| `pytest tests/test_procore_coverage_matrix.py tests/test_procore_query_commands.py tests/test_procore_financial_cli.py` | 0 | 38 passed (existing coverage tests unaffected) |
| `pytest -m "not live" tests/test_procore*.py` | 0 | 745 passed, 1 deselected (no regression; +9) |
| `ruff check src/hb_assistant/procore/coverage.py src/hb_assistant/cli/procore.py` | 0 | All checks passed |
| `mypy src` | 0 | Success: no issues in 143 source files |
| `hb-assistant procore validate --json` | 0 | ok, 28/28 |
| `hb-assistant procore live coverage-matrix --payloads-dir … --json` | 0 | 17 families / 59 endpoints / 5 sampled |

---

## 5. Guardrail attestations

- **No raw Procore response values** in the matrix or evidence (names/types/counts only;
  secret/raw-value scan = 0). Stop condition structurally prevented.
- **No Procore/M365 writeback**; **no live Procore call** (`HB_PROCORE_LIVE` unset); no DB writes —
  the matrix is a pure read model over the registry + normalizers (run on local synthetic samples).
- **No tokens, signed URLs, or PEMs** emitted; attachment URLs are never surfaced (names only).
- **No legal/claims/financial/safety/entitlement/schedule-impact determination** — coverage is an
  intelligence/review aid; the `_FAMILY_PROJECTION` map is a documented coarse capability aid.
- **Held endpoints untouched** (`budget-details` reports `registered: false`, contract-only).
