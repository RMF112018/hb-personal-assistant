# Phase 04B — Daily-Log Endpoint Resolution (paths + real field contracts + entity enrichment + live verify)

**Date:** 2026-05-29 · **Project:** `tropical` (`2525840`, pilot) ·
**HEAD at start:** `48dbcc4…` (Prompt 00 baseline).

Prompt 00 found the daily-log endpoints returned **0 records** on the `tropical` capture and their
normalizer field contracts were unverified guesses. The operator supplied the **real Procore
request/response contracts** for every daily-log sub-log. This change makes the endpoints faithful
and safe, projects rich entities, and **live-verifies all 11 via smoke**.

## 1. Path correction

| endpoint | before | after |
|---|---|---|
| `daily-log-weather` | `/rest/v1.0/projects/{project_id}/weather_logs` | **`/rest/v1.1/projects/{project_id}/daily_logs/weather_logs`** |

The other six existing paths matched the supplied examples and are unchanged. The corrected weather
path is validated by its smoke (a wrong path would 404 → `transport_error`; it returned 200).

## 2. New endpoints added (4)

| endpoint id | path | sensitivity | routing |
|---|---|---|---|
| `daily-log-accident-review-routed` | `/rest/v1.0/projects/{project_id}/accident_logs` | critical | review + safety_route |
| `daily-log-dumpster` | `/rest/v1.0/projects/{project_id}/dumpster_logs` | low | — |
| `daily-log-safety-violation-review-routed` | `/rest/v1.0/projects/{project_id}/safety_violation_logs` | critical | review + safety_route |
| `daily-log-visitor` | `/rest/v1.0/projects/{project_id}/visitor_logs` | high | review (subject = visitor name → hashed) |

Canonical registry total: **23 → 27** endpoints (registry + live-gate count assertions updated).
`injury_logs` is referenced in the legacy selection seed but **no contract was supplied** — documented
here as a follow-up, **not** added.

## 3. Normalizer rewrite + entity projection

The active live path used thin inline `_normalize_daily_log_*` functions in `live_sync.py` (wired via
`_NORMALIZER_BY_ID`). Those are **removed** and replaced by:

- `src/hb_assistant/procore/normalizers/daily_log_live.py` — 11 per-section normalizers with the real
  field contracts.
- `src/hb_assistant/procore/normalizers/entities.py` — shared PII-safe projection helpers
  (person/company/location/segment/attachment/custom-field entities + relationship edges + action
  signals), reusing the `hashing.py` primitives.

Each record's `canonical_fields` now carries: real scalar fields + `*_summary` hashes for free text +
an `entities` block + derived `edges` + `action_signals`. Persistence is unchanged (single
`canonical_json_redacted` column; `raw_body_persisted=0`).

**PII / redaction posture (per real payloads):**
- People (`created_by`, `user`, `contact`, `inspector_name`, `involved_name`) → hashed person
  entities `{role, hash_prefix, id?}` — never name/email/phone.
- Free text (`comment`/`comments`/`notes`/`details`/`safety_notice`/`contents`, visitor `subject`,
  `daily_log_segment.description`) → `*_summary` SHA-256 blocks.
- Attachments → `{id, filename_summary, *_url_path, content_type}`; **all URLs
  (`url`/`share_url`/`viewable_url`/`thumbnail_url`) stripped to path-only** — no scheme, no query
  strings carrying `company_id` / `prostore_file_id` / signed tokens.
- `custom_fields` → typed: string hashed; decimal/boolean/lov preserved.
- `vendor`/`trade`/`cost_code`/`location`/`daily_log_segment` → entities (org/place labels, not
  personal PII, kept verbatim — matching the existing inspection/punch-item posture).
- Action signals (PII-free strings): `weather_delay`, `issue_day`, `delay`, `safety`,
  `compliance_due_set`.

## 4. Live smoke verification (operator-authorized GET, no SQLite write, no raw dump)

`auth refresh` (cached token had expired) → then for each endpoint:
`HB_PROCORE_LIVE=1 hb-assistant procore live smoke --project tropical --endpoint <id>
--max-pages 1 --max-items 10 --confirm-live-get --json`.

All 11 returned `state=success` (HTTP 200). `retrieved_count=0` is expected — these daily-log sections
are unused on `tropical` at this time; a 200 with 0 records still proves the path + auth + gate.
Receipts (redacted — sync_run_id prefix only):

| endpoint | state | retrieved | sync_run_id |
|---|---|---|---|
| daily-log-weather | success | 0 | `26762b35…` |
| daily-log-manpower | success | 0 | `22391cff…` |
| daily-log-notes | success | 0 | `f5e0e409…` |
| daily-log-deliveries | success | 0 | `ec249d59…` |
| daily-log-delays-review-routed | success | 0 | `c31a788f…` |
| daily-log-inspections | success | 0 | `6ea9b013…` |
| daily-log-dcrs | success | 0 | `95f5a809…` |
| daily-log-accident-review-routed | success | 0 | `b9538451…` |
| daily-log-dumpster | success | 0 | `7a99ff77…` |
| daily-log-safety-violation-review-routed | success | 0 | `1cc4bd61…` |
| daily-log-visitor | success | 0 | `e968273f…` |

Each adapter's `verification_reason` was updated to `live_smoke_passed_2026-05-29:<run>` accordingly.

## 5. Tests + stack

- New `tests/test_procore_daily_log_live_normalizer.py` (13 tests): scalar contracts, PII hashing,
  attachment URL path-only, custom-field typing, entity/edge/action-signal projection, safety routing,
  and a no-raw-text-leak JSON assertion per section.
- Updated `tests/test_procore_live_sync_verified_chain.py` (delays/notes/manpower) to the real field
  names + routing reasons (they previously asserted the unverified guesses).
- Count assertions updated: `test_procore_endpoint_registry.py` `_CANONICAL_IDS` (+4) and
  `test_procore_live_gate.py` (`23` → `27`).
- `hb-assistant procore validate` → 28/28. Repo sensitive scan → **0 findings** in the new
  `daily_log_live.py` / `entities.py` / new test (the only matches in edited files are the
  pre-existing `_setup_env` test-harness env pattern).

## 6. Known divergences (out of scope, for follow-up)

- The legacy Phase-03 aggregate path (`normalizers/daily_log.py` +
  `resources/config/procore_daily_log_selection.seed.yaml`, used by `sync.py`) still carries the
  earlier weather whitelist (`temperature`/`conditions`/`wind_speed`/…) and section set
  (incl. `injury`). It targets the single `/daily_logs` aggregate endpoint, not the per-section flat
  endpoints corrected here, and is **left untouched**.
- `injury_logs` endpoint: no operator contract supplied → not added.
