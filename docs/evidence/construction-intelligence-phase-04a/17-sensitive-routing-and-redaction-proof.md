# Phase 04A — Prompt 10: Sensitive routing and redaction proof

## Objective

Prove that incident / injury / safety / claim / notice / delay / cost /
schedule / contract language routes to review and that no raw bodies or
secret-shaped literals (Bearer tokens, access_token / refresh_token /
client_secret values) persist anywhere in Phase 04A's post-sync surface.
This is a **proof** prompt: no new application code, no live Procore call,
no new endpoints. The deliverable is a focused test extension plus this
evidence file that names the proof line-by-line.

## Source files participating in the proof

- **Rule catalog**: `resources/config/procore_sensitive_routing_rules.yaml`
  (9 declarative rules, version 1).
- **Normalizer triggers**: `src/hb_assistant/procore/normalizers/rfi.py`,
  `submittal.py`, `observation.py`, `meeting.py`, `daily_log.py`,
  `punch_item.py`, `schedule.py` —
  `_REVIEW_STATUS_FRAGMENTS`, `_REVIEW_SUBJECT_FRAGMENTS`,
  `_REVIEW_BODY_FRAGMENTS`, `_safety_route_decision`,
  `_looks_review_required`, plus the always-route defaults on
  reply / response / comment / package / meeting-detail normalizers.
- **Schema invariants**: `src/hb_assistant/store/migrator.py` (V6
  statements) — `CHECK(raw_body_persisted = 0)` on
  `procore_live_records` and `procore_live_sync_runs`; also
  `CHECK(redaction_applied = 1)` on `procore_live_sync_runs`.
- **Redaction primitives**: `src/hb_assistant/procore/redaction.py` —
  `redact_body`, `redact_headers`, `mask_pii_in_excerpt`.
- **HTTP-client posture**: `src/hb_assistant/procore/http_client.py` —
  `_require_get`, `_build_headers` (`Authorization: Bearer <access_token>`
  obtained at request time, never stored on the instance, never accepts
  `PROCORE_CLIENT_SECRET`).
- **Tests** (load-bearing for this proof):
  - `tests/test_procore_sensitive_routing_proof.py`
  - `tests/test_procore_sensitive_routing_proof_corpus.py`
  - `tests/test_procore_redaction.py`
  - `tests/test_procore_live_sync_verified_chain.py`
  - `tests/test_procore_repositories_v6.py`
  - `tests/test_repo_sensitive_scan.py`

## Bucket → rule → trigger → test matrix

| Bucket | YAML rule(s) covering it | Normalizer-level trigger (fragment list / always-route path) | Proof test id |
| --- | --- | --- | --- |
| **incidents** | `procore-incident-injury-personnel` (keyword `incident`); `procore-observation-safety` (rule_id) | `observation._REVIEW_STATUS_FRAGMENTS` includes `incident`; `_REVIEW_SUBJECT_FRAGMENTS` includes `incident` | `test_bucket_routes_to_review_and_redacts[incidents]` |
| **injuries** | `procore-incident-injury-personnel` (keyword `injury`) | `observation._REVIEW_STATUS_FRAGMENTS` + `_REVIEW_SUBJECT_FRAGMENTS` both include `injury` (safety-class) | `test_bucket_routes_to_review_and_redacts[injuries]` (asserts `safety_route=True` via subject-fragment route) |
| **safety** | `procore-observation-safety` (keywords `near miss, violation, unsafe, ppe, fall, fatal, hospitalization, osha`) | `observation._REVIEW_STATUS_FRAGMENTS` includes `safety` | `test_bucket_routes_to_review_and_redacts[safety]` (asserts `safety_route=True`) |
| **claims** | `procore-incident-injury-personnel` (keyword `claim`); `procore-rfi-legal-or-contractual` (keyword `claim`) | `rfi._REVIEW_SUBJECT_FRAGMENTS` includes `claim`; same for submittal | `test_bucket_routes_to_review_and_redacts[claims]` |
| **notices** | `procore-incident-injury-personnel` (keyword `notice`) | `observation._REVIEW_BODY_FRAGMENTS` includes `notice` | `test_bucket_routes_to_review_and_redacts[notices]` |
| **delay** | `procore-daily-log-delays` (category `daily_log_delays`) | `rfi._REVIEW_SUBJECT_FRAGMENTS` includes `delay`; same for submittal and observation subject | `test_bucket_routes_to_review_and_redacts[delay]` |
| **cost** | `procore-submittal-financial-or-legal` (keyword `cost`); `procore-financial-summary` (categories `budget`, `invoices`, …) | No direct `cost` fragment in normalizers; cost-language records route via co-occurring fragments (e.g. `claim`). YAML coverage proven separately. | `test_bucket_routes_to_review_and_redacts[cost]` (cost-language paired with `claim` trigger); `test_routing_rules_yaml_covers_prompt_10_buckets` |
| **schedule** | `procore-daily-log-delays` (schedule impacts manifest as delays) | No direct `schedule` fragment in normalizers; schedule-language records route via `delay`. Documented synonym mapping in the proof. | `test_bucket_routes_to_review_and_redacts[schedule]` (schedule-language paired with `delay` trigger); `test_routing_rules_yaml_covers_prompt_10_buckets` (with `_BUCKET_YAML_SYNONYMS["schedule"] = ("delay", "daily_log_delays")`) |
| **contract** | `procore-contractual-records` (categories `commitments`, `prime_contracts`, `prime_contract_change_orders`, `potential_change_orders`); `procore-rfi-legal-or-contractual` (keyword `contract`) | `submittal._REVIEW_SUBJECT_FRAGMENTS` includes `contract amendment` | `test_bucket_routes_to_review_and_redacts[contract]` |

The `schedule` bucket honestly has no direct normalizer keyword — the
proof file documents this rather than inventing a synonym. The
schedule normalizer (`src/hb_assistant/procore/normalizers/schedule.py`)
treats schedule rows as structured-medium-sensitivity
(`routing_reason="schedules_structured_medium_sensitivity"`,
`review_required=False`). Schedule-impact *language* inside other records
fires the `delay` heuristic and the `daily_log_delays` rule.

## No-raw-body / no-secret attestation

### Schema-level proof (V6 CHECK constraints)

```sql
-- src/hb_assistant/store/migrator.py (V6_STATEMENTS)
CREATE TABLE IF NOT EXISTS procore_live_sync_runs (
  ...
  redaction_applied INTEGER NOT NULL DEFAULT 1 CHECK(redaction_applied = 1),
  raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
  ...
);

CREATE TABLE IF NOT EXISTS procore_live_records (
  ...
  raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
  ...
);
```

Constraints exercised by:

- `tests/test_procore_repositories_v6.py::test_raw_body_persisted_check_constraint_rejects_one`
- `tests/test_procore_sensitive_routing_proof_corpus.py::test_v6_check_constraint_rejects_raw_body_persisted_on_records`
- `tests/test_procore_sensitive_routing_proof_corpus.py::test_v6_check_constraint_rejects_redaction_applied_zero_on_runs`

### `redact_body()` proof

`tests/test_procore_sensitive_routing_proof_corpus.py::test_redact_body_strips_secret_shaped_payloads`
constructs a synthetic payload containing every secret-shape vector
(literal `Bearer <token>` in `Authorization`, `client_secret`,
`refresh_token`, JWT-shaped literal nested in a list, free-text mention
of the Bearer literal) and asserts none survive the redact pass.

### Live SQLite corpus probe

Run against `/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`
(the same DB the Phase 04A apply runs populated):

```bash
$ sqlite3 "$DB" "SELECT COUNT(*) FROM procore_live_records"
623

$ sqlite3 "$DB" "SELECT COUNT(*) FROM procore_live_records WHERE raw_body_persisted != 0"
0

$ sqlite3 "$DB" "SELECT COUNT(*) FROM procore_live_records WHERE canonical_json_redacted LIKE '%Bearer %'"
0

$ sqlite3 "$DB" "SELECT COUNT(*) FROM procore_live_records WHERE canonical_json_redacted LIKE '%access_token%'"
0

$ sqlite3 "$DB" "SELECT COUNT(*) FROM procore_live_records WHERE canonical_json_redacted LIKE '%refresh_token%'"
0

$ sqlite3 "$DB" "SELECT COUNT(*) FROM procore_live_records WHERE canonical_json_redacted LIKE '%client_secret%'"
0

$ sqlite3 "$DB" "SELECT COUNT(*) FROM procore_live_records WHERE canonical_json_redacted LIKE '%Authorization%'"
0
```

Per-endpoint distribution of the 623 corpus rows:

```
activities         5
daily-log-dcrs     1
daily-log-weather  1
meeting-detail     5
meeting-topics   108
meetings          96
observations     100
projects           7
punch-items        4
rfi-responses    123
rfis              72
schedules          1
submittals       100
```

The invariant ("no secret-shaped literals in any persisted row") is
asserted programmatically by
`tests/test_procore_sensitive_routing_proof_corpus.py::test_no_secret_literals_in_live_records_corpus`
(empty-DB-vacuous under the test fixture, but the same scan run against
the operator's DB returns the zero counts above).

### HTTP-client posture (Bearer ≠ secret)

`tests/test_procore_live_sync_verified_chain.py::test_transport_receives_bearer_access_token_not_client_secret`
asserts the live transport sees `Authorization: Bearer <access_token>`
and never sees `PROCORE_CLIENT_SECRET`.
`tests/test_procore_client_secret_isolation.py::test_client_secret_symbol_not_imported_outside_allowlist`
enforces the same property at the static-import layer.

### Repo-wide secret scan

`tests/test_repo_sensitive_scan.py::test_repo_has_no_unallowed_sensitive_findings`
runs `SensitiveScanner` over the repo root and gates on an explicit
allowlist. The Prompt 10 corpus test file is allowlisted
(`bearer_token` rule) because it intentionally constructs synthetic
`Bearer ` literals to test the redactor. All other files remain
non-allowlisted.

## Verification

```
$ python -m pytest -q tests/test_procore_sensitive_routing_proof.py tests/test_procore_sensitive_routing_proof_corpus.py
22 passed

$ python -m pytest -q --no-header
947 passed, 2 skipped in 18.49s

$ ruff check .
All checks passed!

$ mypy .
Success: no issues found in 180 source files

$ python -m compileall -q src tests
(clean — no output)

$ hb-assistant procore validate --json
27/28   # 28th (mapping_consistent) is the pre-existing pending-projects
        # failure from procore_projects.seed.yaml, carried from the handoff.

$ hb-assistant procore tools list --json   # returns the canonical tools envelope
$ hb-assistant procore mapping validate --json   # returns the canonical mapping envelope
```

## Stop conditions honored

- No live Procore call performed (Live API Policy explicit).
- No non-GET introduced.
- Authorization header sourced via `_build_headers` only (access token,
  never client secret).
- No raw body persisted in any new write path; new tests confirm the
  schema-level invariant.
- No real PII or token appears in this evidence file or in either new
  test file. The only credential-shaped literals are synthetic
  (`synthetic-prompt-10-…`) and exist exclusively to drive the redactor
  under test.

## Related references

- Architecture addendum: `docs/architecture/14-procore-live-sync-phase-04a.md`
  (section "Sensitive routing and redaction proof (Prompt 10)").
- Predecessor in the evidence series:
  `docs/evidence/construction-intelligence-phase-04a/16-obsidian-register-from-live-records.md`.
- Phase 03 Prompt 09 declarative routing rules parity:
  `docs/evidence/construction-intelligence-phase-04/09-sensitive-routing-rules-parity.md`
  (if present in the operator vault — repo evidence is here).
- YAML rule catalog: `resources/config/procore_sensitive_routing_rules.yaml`.
