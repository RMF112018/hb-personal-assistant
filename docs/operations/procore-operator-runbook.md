# Procore Operator Runbook

Authoritative operator surface for the `hb-assistant procore` CLI. Every
command is read-only against external systems. Every potentially-mutating
command defaults to `--dry-run`. Every command returns structured JSON by
default; pass `--no-json` for a compact human-readable summary.

**Posture (Phase 03):** local-first, Bobby-only MVP. The Procore HTTP
surface is GET-only by construction (writeback endpoints cannot be
loaded). Live OAuth is opt-in and manual. The deterministic controller
policy + `procore_sensitive_routing_rules.yaml` route all sensitive
material to the review queue — no model decisioning on contracts,
financials, incidents, injury, or personnel data.

**Companion surfaces:** see also `construction-agent-operator-runbook.md`
(SharePoint / OneDrive / Outlook ingestion) and
`mvp-local-runtime-operator-guide.md` (local-runtime setup).

**Phase 04A Prompt 01 (2026-05-28):** `HB_PROCORE_LIVE` env-var gate is
now required for the two existing live-execution paths. The CLI fails
closed with exit code 2 and a redacted stderr message of the form
`ERROR: live execution requires HB_PROCORE_LIVE=1; command=<...> refused`
when an operator runs `procore audit execute --confirm` or
`procore sync run --apply --confirm` without first exporting
`HB_PROCORE_LIVE=1`. The gate is exact-match on the literal string `"1"`
— values like `"true"`, `"yes"`, or `"on"` are treated as inactive by
design. Dry-run workflows (`procore audit dry-run`, default
`procore sync run`, `tools list`, `mapping validate`, `obsidian preview`,
`validate`) are unaffected and continue to work with no env-var
required. A second runtime check (`assert_live_mapping_strict`) fires
immediately after the env-var gate on `sync run --apply` and refuses to
proceed against any target whose mapping is pending, unknown, or
non-pilot (exit code 3). See evidence
`docs/evidence/construction-intelligence-phase-04a/01-live-readiness-hardening.md`.

**Phase 04A baseline (2026-05-28):** The Procore Live Enablement arc opens
at commit `e90a5e2` (Phase 04 closeout). Phase 04A Prompt 00 is a
verification-only rebaseline — no CLI surface changes, no guardrail
changes, no live transport wiring yet. The default `ProcoreHTTPClient`
transport still raises `transport_not_injected`; no `procore live`
subgroup or `procore live smoke` command exists at this baseline. Future
Phase 04A prompts introduce the production-wired transport (item 05-A)
and live-gated probes — those changes will land behind `HB_PROCORE_LIVE=1`
+ `--confirm-live-get` and will be documented in this runbook when they
ship. See evidence
`docs/evidence/construction-intelligence-phase-04a/00-rebaseline-readiness.md`.

**Phase 04A Prompt 03A (2026-05-28):** the canonical operator contract now
surfaces under `hb-assistant procore live` with two explicit commands:
`live endpoints list --json` and `live sync --project <key> --endpoint <alias>
--apply --sqlite-only --max-pages N --max-items N --confirm-live-get --json`.
This prompt is **contract-only + fail-closed**: no live Procore HTTP is
performed even when all live flags are present. Endpoint visibility and
execution readiness are intentionally decoupled. Every endpoint appears in
`live endpoints list` with deterministic state (`operational`,
`not_live_verified`, `fail_closed_unsupported`) and explicit reason codes.
`live sync` receipts now always include stable counters
(`request_count/retrieved_count/normalized_count/sqlite_upsert_count/sqlite_total_count`);
for fail-closed responses all counters are zero by design.

## Environment variables

| Var | Purpose | Set when |
| --- | --- | --- |
| `PROCORE_CLIENT_ID` | Public Procore client id (presence checked by `procore auth status`; value never logged) | Operator is preparing future live OAuth |
| `PROCORE_CLIENT_SECRET` | Secret — **prefer macOS Keychain** (`security add-generic-password -s hb-assistant-procore -a client-secret -w`). Env var is the fallback. Never in repo, evidence, or SQLite. | Operator must run a live audit/sync (still opt-in manual) |
| `PROCORE_REFRESH_TOKEN` | Token cache surrogate; presence-only check | Operator has completed manual OAuth flow |
| `HB_PROCORE_ENDPOINT_CONTRACT` | Override path to the endpoint-contract YAML | Testing or overriding the seeded contract |
| `HB_PROCORE_PROJECTS` | Override path to the projects-registry YAML | Testing or overriding the seeded mapping |
| `HB_CONSTRUCTION_VAULT_ROOT` | Required for `procore obsidian preview --apply` | Operator wants procore-*.md projections written to the local vault |

When a variable is unset, the seeded file under `resources/config/` wins,
with an optional repo-local override at `config/<name>.yml` taking
precedence over the seed.

## Lifecycle

### Phase 1 — Discovery & readiness

```bash
# Single read-only stack-readiness check. Cross-checks seeds, mapping,
# redaction module, Obsidian renderer + templates, vault writer posture,
# schema version, procore tables, and auth-credential presence. No live
# call. Exit 0 on green, 1 on any failure.
hb-assistant procore validate --json

# Tighten pass criteria: env_absent/env_partial auth and missing
# procore_* tables become hard failures. Never enables any I/O.
hb-assistant procore validate --strict --json

# Auth credentials presence check (no network).
hb-assistant procore auth status --json

# Mapping consistency: pending pilots flagged as informational exit 1.
hb-assistant procore mapping validate --json
hb-assistant procore mapping list --json
```

### Phase 2 — Contract & endpoint audit

```bash
# Loaded endpoint catalog (category, sensitivity, status).
hb-assistant procore tools list --json

# Dry-run access matrix for one HB project. Verdicts: would_audit,
# sensitive_review_required, excluded, deferred, project_not_mapped.
hb-assistant procore tools audit --project tropical --json

# Per-endpoint dry-run receipt with redacted envelope (no network).
hb-assistant procore audit dry-run --project tropical --json

# EXPLICIT manual live opt-in. Still GET-only and fully redacted.
# Requires --confirm. Never runs in tests or CI.
hb-assistant procore audit execute --project tropical --confirm --json
```

### Phase 3 — Pilot sync

```bash
# Dry-run plan (default): redacted, zero side effects.
hb-assistant procore sync run --project tropical --json

# Dry-run plan filtered to a specific endpoint (Phase 04 Prompt 04). The
# --endpoints / -e flag is repeatable. The RFI dry-run receipt carries
# normalization_schema_version + would_persist_children_separately so the
# operator can confirm the canonical normalizer is wired before any apply.
hb-assistant procore sync run --project tropical --dry-run \
  --endpoints list-rfis --json

# EXPLICIT opt-in apply. Writes normalized rows to LOCAL SQLite only
# after the Prompt 07 audit gate passes. Never mutates Procore.
hb-assistant procore sync run --project tropical --apply --confirm --json
```

For the RFI endpoint specifically, `--apply` persists each RFI as a
`category="rfis"` row and each nested reply as a separate
`category="rfi_replies"` row with `review_required=True` (replies are always
routed for review per the prompt stop-condition). Body text is never persisted
— reply bodies are reduced to SHA-256 hash-prefix summaries.

For the submittal endpoint (Phase 04 Prompt 05), the same pattern applies with
three target categories: parents land as `category="submittals"`, each nested
response lands as `category="submittal_responses"` (always `review_required=True`),
and each nested package lands as `category="submittal_packages"` (always
`review_required=True`). Response comment bodies and package descriptions are
never persisted — both are reduced to SHA-256 hash-prefix summaries via the
same normalizer helper used for RFI replies.

```bash
# Submittal dry-run plan
hb-assistant procore sync run --project tropical --dry-run \
  --endpoints list-submittals --json
```

For the observation endpoint (Phase 04 Prompt 06), the endpoint ships as
`verification_status: candidate` → `is_live_eligible: false`. `--apply` will
emit `skipped_not_live_eligible` for observations until a future prompt
promotes the verification status to `official_docs_verified` after live docs
reconciliation. The dry-run path still surfaces the endpoint with full
normalization metadata. The normalizer's safety routing scans the status,
type, subtype, title, and description fields for safety / incident / injury /
near-miss / corrective-action / unsafe / violation / PPE / personnel keywords;
any hit sets `review_required=true` and `safety_route=true` on the canonical
record. Descriptions are never persisted as raw text — they're reduced to
SHA-256 hash-only summaries, and the redacted excerpt is derived from the
title only.

```bash
# Observation dry-run plan
hb-assistant procore sync run --project tropical --dry-run \
  --endpoints list-observations --json
```

For the meeting + meeting-topic endpoints (Phase 04 Prompt 07), both ship as
`verification_status: candidate` → `is_live_eligible: false`. Meetings and
meeting-topics are **two separate Procore endpoints** (not parent + nested
children). The meeting parent normalizer is metadata-only (title / time /
location / organizer); review routing fires on claim / delay /
change-order / legal / financial title or status fragments. The meeting-topic
normalizer additionally scans the description and `action_items` (string or
list) for safety / incident / injury / corrective-action / claim / delay /
cost / unsafe / PPE / fall keywords; descriptions and action items are reduced
to SHA-256 hash-only summaries and never persisted as raw text.

```bash
# Meeting dry-run plan
hb-assistant procore sync run --project tropical --dry-run \
  --endpoints list-meetings --json

# Meeting-topic dry-run plan
hb-assistant procore sync run --project tropical --dry-run \
  --endpoints list-meeting-topics --json
```

The meeting-topics path template carries a `{meeting_id}` placeholder. Live
execution will require threading the parent meeting id through the paginator
when the endpoint is promoted; until then, the candidate posture keeps
`apply()` short-circuiting via `skipped_not_live_eligible`.

For the daily log endpoint (Phase 04 Prompt 08), `list-daily-logs` is already
verified and live-eligible. The normalizer demultiplexes each daily log
payload into per-section canonical rows guided by the section selection scope
at `resources/config/procore_daily_log_selection.seed.yaml`. Three buckets:

- **Selected sections** (counts, weather, manpower, DCR, delivery) persist
  as canonical rows with a declared `canonical_field_keys` whitelist and
  `review_required=False`.
- **Review-only sections** (`notes`) persist with `review_required=True` and
  a SHA-256 hash-only `body_summary` — note text is never stored raw.
- **Routed-to-review sections** (`accident`, `injury`, `delay`,
  `safety_violation`) persist with `review_required=True` AND
  `safety_route=True` AND a SHA-256 hash-only `body_summary`. Accident /
  injury / delay / safety text **never enters normal canonical rows** by
  construction — the bucket assignment is structural, not derived from
  content.

```bash
# Daily log dry-run plan
hb-assistant procore sync run --project tropical --dry-run \
  --endpoints list-daily-logs --json
```

The dry-run receipt entry surfaces `would_persist_sections_separately: true`,
`normalization_schema_version`, and (when a `daily_log_preview_payload` is
threaded) per-category `planned_records_by_category` counts. Override the
selection scope locally with `HB_PROCORE_DAILY_LOG_SELECTION=/path/to/file.yml`
or a repo-local `config/procore_daily_log_selection.yml`.

### Phase 4 — Obsidian projection

```bash
# Dry-run preview (default): rendered Markdown + paths + redacted
# samples + review-routing summary. No vault writes.
hb-assistant procore obsidian preview tropical --json

# EXPLICIT opt-in apply. Writes hybrid procore-*.md alongside legacy
# notes in 01_Projects/ + sensitive items into 02_Review_Queue/.
# Requires --confirm and HB_CONSTRUCTION_VAULT_ROOT.
HB_CONSTRUCTION_VAULT_ROOT="$VAULT" \
  hb-assistant procore obsidian preview tropical --apply --confirm --json
```

### Phase 5 — Verification & troubleshooting

```bash
# Re-run after any config or env change. `--strict` is the canonical
# green-light gate before any manual live audit/sync.
hb-assistant procore validate --strict --json

# Inspect a specific check by name (no separate command — the envelope
# carries every check inline; pipe through jq):
hb-assistant procore validate --json | jq '.checks[] | select(.name == "mapping_consistent")'

# Compact human-readable form:
hb-assistant procore validate --no-json
```

The validator runs eleven checks: `seed_endpoint_contract_loadable`,
`seed_projects_loadable`, `mapping_consistent`, `app_profile_loadable`,
`auth_status_present`, `redaction_module_importable`,
`obsidian_templates_resolvable`, `obsidian_routing_rules_loadable`,
`vault_root_configurable`, `sqlite_schema_at_expected_version`,
`procore_tables_present`. Each check exposes `{name, ok, detail?,
error_redacted?}`; failures redact every exception value to the
exception class name only (no message text leaks).

## Command summary

| Group | Command | Side effects |
| --- | --- | --- |
| `auth` | `status` | none (read-only; presence-only check) |
| `tools` | `list`, `audit` | none (read-only projection) |
| `mapping` | `validate`, `list` | none (read-only) |
| `projects` | `list` | none |
| `companies` | `list` | none |
| `audit` | `dry-run`, `execute` | `execute` is manual live GET-only with `--confirm` |
| `sync` | `run` | `--apply` writes to local SQLite only; audit gate required |
| `obsidian` | `preview` | `--apply` writes procore-*.md to local vault only |
| `validate` | (top-level) | none (read-only; idempotent inspection) |

## Dry-run / apply convention

- Every potentially-mutating command defaults to `--dry-run`.
- `--apply` is opt-in. In non-TTY contexts a separate `--confirm` flag
  is mandatory (matches `construction-agent` posture).
- `audit execute` requires `--confirm` unconditionally — it is the only
  surface that issues live HTTP, and even then it is GET-only and fully
  redacted.
- SQLite writes are local-only and reversible (delete the local DB to
  reset state).
- Vault writes are atomic (tempfile + `os.replace`) and marker-bounded
  (`<!-- HB-PROCORE-...:START -->` / `:END`).
- Phase 04 Prompt 10 added two more marker-bounded artifacts:
  `HB-PROCORE-OBSERVATION-REGISTER` (per-project observation table; safety-
  routed rows excluded by `safety_route` flag) and `HB-PROCORE-MEETING-
  REGISTER` (meetings + topics; sensitive topics routed by
  `procore_sensitive_routing_rules.yaml`). The existing
  `HB-PROCORE-DAILY-LOG` artifact is now section-aware — its rows surface
  the daily-log section, bucket, review/safety flags, and a body-hash
  fingerprint (never raw body text). All three honor the same dry-run /
  apply / confirm convention as the original 7 procore artifacts.

## What is never written / never logged

- Procore is never mutated. There is no `POST`, `PUT`, `PATCH`, or
  `DELETE` path in the entire MVP; the endpoint contract enforces
  `http_method: GET` at load time.
- SharePoint, OneDrive, and Outlook are likewise never written.
- Tokens, client secrets, refresh tokens, and `Authorization` headers
  never appear in repo, evidence, logs, SQLite plaintext columns, or
  Obsidian notes. Headers are redacted at the HTTP boundary; bodies
  are reduced to structural summaries or bounded hashes.
- Full Procore response bodies never appear in Obsidian projections.
  Sensitive material (financials, contracts, incidents, injury,
  personnel, daily-log delays) is routed exclusively to the review
  queue by controller policy + `procore_sensitive_routing_rules.yaml`
  — never by the model.
- Phase 04 Prompt 09 extended `procore_sensitive_routing_rules.yaml`
  with five family-scoped rules (`procore-rfi-legal-or-contractual`,
  `procore-submittal-financial-or-legal`, `procore-observation-safety`,
  `procore-meeting-sensitive-topic`, `procore-daily-log-personnel-pii`)
  for declarative parity with the per-entity normalizers. The validate
  check `sensitive_routing_rules_cover_phase_04_families` asserts every
  family appears in a rule_id. The proof artifact lives at
  `docs/evidence/construction-intelligence-phase-04/sensitive-routing-proof.md`
  — operators can read it to confirm that raw text / email / phone /
  token literals never leave the normalizer hash boundary.

## Recovery

- If `procore validate --strict --json` reports any failure, the
  envelope's `checks[].error_redacted.error_fields.error_type` (when
  present) names the exception class; the seeded YAMLs and the
  per-module unit tests are the next stop. The validator never raises
  out of the CLI process — it always returns the envelope with a
  non-zero exit code.
- If `procore obsidian preview --apply` reports `vault_root_unconfigured`,
  set `HB_CONSTRUCTION_VAULT_ROOT` and re-run.
- If a fresh SQLite has no `procore_*` tables, run `procore sync run`
  once in dry-run, then `--apply --confirm` — the sync coordinator
  creates the tables on demand.

## Access token (Phase 04 Prompt 01)

The Procore HTTP client requires an OAuth access token. It will **not** reuse
the OAuth client secret as a bearer credential. If no access token is
available the first request fails closed with `ProcoreAuthRequired`. OAuth
token-exchange itself is deferred to a later prompt; until then the operator
supplies a token directly via one of:

```bash
# Preferred (macOS Keychain — never echoed, never in repo)
security add-generic-password -s 'hb-assistant-procore' -a 'access-token' -w

# Alternative (current shell)
export PROCORE_ACCESS_TOKEN='your-access-token'
```

The existing `PROCORE_CLIENT_SECRET` env / Keychain account remains in place
for future OAuth bootstrap but is no longer accepted as a bearer credential.

### First-time OAuth login (Phase 04 Prompt 02 acquisition)

1. Ensure `PROCORE_CLIENT_ID` is set in `procore_app_profile.seed.yaml` and
   the client secret is in macOS Keychain (`security add-generic-password
   -s 'hb-assistant-procore' -a 'client-secret' -w`) or env
   `PROCORE_CLIENT_SECRET`.
2. Run `hb-assistant procore auth login`. The CLI prints the Procore
   authorization URL — open it in a browser, sign in, approve the app, and
   copy the displayed authorization code.
3. Paste the code at the CLI prompt (or supply it via
   `--code <code>` if scripting). The CLI exchanges the code at
   `<oauth_base>/oauth/token`, writes the resulting access + refresh tokens
   to the local cache, and emits a redacted success envelope (no token
   values).
4. From here on, the default token-provider chain
   (`env_or_keychain → oauth_refreshing → missing`) handles refresh
   transparently as access tokens near expiry.

Refresh manually with `hb-assistant procore auth refresh`. Remove the
cache with `hb-assistant procore auth logout`.

### OAuth token cache (Phase 04 Prompt 02)

The HTTP client also reads a local OAuth token cache (read-only) at:

```
~/Library/Application Support/HB Personal Assistant/auth/procore_token.json
```

Expected JSON shape (extra keys are tolerated):

```json
{"access_token": "<token>", "expires_at": "<ISO 8601 UTC>"}
```

The cache file must be `0600` (owner-only). The token provider lookup order is
**env / Keychain → cache → missing**; the first source that yields a non-empty
token wins. The cache file is consumed only — populating / refreshing it is
**not** yet implemented (manual until a later prompt). An expired or malformed
cache file is silently ignored.

## Pending project sync targets (Phase 04 Prompt 01)

`hb-assistant procore sync run` defaults to mapped pilots only. Projects with
`status: pending` in `procore_project_mapping.seed.yaml` (e.g. `hilltop`,
`hilltop-gardens`) are rejected with `ProcorePendingProjectRejected` unless
the operator passes `--allow-pending` explicitly:

```bash
# Default: mapped pilots only
hb-assistant procore sync run --dry-run --json

# Explicit override for planning against a pending mapping
hb-assistant procore sync run --project hilltop --allow-pending --dry-run --json
```

## Endpoint verification (Phase 04 Prompt 03)

Every Procore endpoint in `resources/config/procore_endpoint_contract.seed.yaml`
now carries structured verification provenance:

| Field | Purpose |
|-------|---------|
| `verification_status` | One of `official_docs_verified`, `candidate`, `unverified`, `excluded_by_guardrail`, `deferred_by_guardrail`. |
| `official_reference_url` | HTTPS URL to the matching Procore developer reference page. Required for included Phase-01 endpoints **unless** `verification_reason` is supplied. |
| `verified_at_utc` | ISO-8601 timestamp when the endpoint was last reconciled against official docs. |
| `verified_by` | Free-text provenance (e.g. `phase-03-prompt-01a`). |
| `live_dry_run_receipt_id` | UUID of the dry-run audit receipt that exercised this endpoint (populated by future prompts). |
| `verification_reason` | Free-text reason permitting a missing URL (only valid in lieu of the URL). |

**Live-eligibility rule.** A `ProcoreEndpoint.is_live_eligible` is `True` only
when `status not in {"excluded", "deferred"}` AND `included_in_phase_01 is True`
AND `verification_status == "official_docs_verified"`. `sync.apply()` skips any
ineligible endpoint with a `skipped_not_live_eligible` receipt entry and never
invokes the transport for it.

Inspect the full catalog (offline, deterministic, redacted):

```bash
hb-assistant procore tools catalog --json
# filter to live-eligible only:
hb-assistant procore tools catalog --json --no-include-ineligible
```

The shipped snapshot is at
`docs/evidence/construction-intelligence-phase-04/03-endpoint-catalog-validation.json`.

## Live-test mode

No live Procore tests ship in this MVP. The `live` pytest marker is reserved
for future work and is gated by `HB_PROCORE_LIVE=1`:

```bash
HB_PROCORE_LIVE=1 python -m pytest -m live -q
```

Without the env var, all `live`-marked tests are skipped. The default
`python -m pytest -q` invocation runs only unmarked offline tests. Full
marker taxonomy and contributor expectations live in
`docs/operations/test-discipline.md`.

## Phase 04A Prompt 03: live GET smoke

The first live Procore API calls land here. Before running:

1. Ensure `hb-assistant procore auth status --json` reports
   `ready_for_live_calls: true` and `cache_present: true`. If the access
   token is expired, the `RefreshingOAuthTokenProvider` will refresh it
   silently using the cached refresh token on the first call — no manual
   action needed.
2. Confirm the pilot mapping: `hb-assistant procore mapping validate --json`
   shows the target project (e.g. `tropical`) with `status=pilot` and a
   non-empty `procore_project_id`.
3. Set `HB_PROCORE_LIVE=1` in the shell that will issue the smoke.

### Smoke command (one per verified endpoint)

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live smoke \
  --project tropical \
  --endpoint <endpoint-id> \
  --max-pages 1 --max-items 5 \
  --confirm-live-get --json
```

Smoke mode does **not** write to SQLite. Verify with:

```bash
hb-assistant procore live records count --project tropical --endpoint <id> --json
# expect count: 0
```

### Interpreting the receipt

Success: `state="success"`, `status="success"`, `http_method="GET"`,
`retrieved_count > 0`, `sqlite_upserted_count == 0`, `redacted_errors == []`.

Transport failure (e.g. wrong path): `state="transport_error"`,
`redacted_errors=[{"code":"http_error","status":<code>}]`. Means the endpoint
adapter's `path_template` does not match Procore's current REST surface;
update `src/hb_assistant/procore/endpoints.py` and re-smoke.

Gate failure: `state="gate_blocked"` with a `reason_codes` list. Re-check the
env var, `--confirm-live-get`, and the pilot mapping.

Not docs-verified: `state="not_live_verified"`,
`no_live_call_performed=true`. The endpoint is in the registry but its
`live_verified` flag is `false`; promote only after a successful smoke.

### Promotion

After a successful smoke, update the adapter's `verification_reason` in
`endpoints.py` to record the receipt id and date:
`live_smoke_passed_<ISO-date>:<receipt-id-prefix>`. After a failed smoke,
flip `live_verified=False` and record
`live_smoke_failed_<ISO-date>:<reason>`.

Latest smoke evidence: `docs/evidence/construction-intelligence-phase-04a/03-live-get-smoke-and-promotion.md`.

## Phase 04A Prompt 04: RFI live apply with reply children

After a successful smoke, apply RFIs (and their replies) to local SQLite:

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical \
  --endpoint rfis \
  --apply --sqlite-only \
  --max-pages 1 --max-items 5 \
  --confirm-live-get --json
```

The orchestrator issues one GET to `/rest/v1.0/projects/{id}/rfis` for the
parent list, then issues one GET per parent at
`/rest/v1.0/projects/{id}/rfis/{rfi_id}/replies`. Replies persist as rows
with `endpoint_id="rfi-responses"` and `parent_procore_id=<rfi_id>` set.
Child fetch is capped internally at `max_pages=1, max_items=50` per parent.
A 4xx on one child fetch increments `child_errors_count` and continues to
the next parent — the run is not aborted.

Receipt fields specific to this path:

- `parent_retrieved_count`, `parent_normalized_count`, `parent_upserted_count`
- `child_endpoint_id` (`"rfi-responses"`), `child_retrieved_count`,
  `child_normalized_count`, `child_upserted_count`, `child_errors_count`

Verify persistence:

```bash
hb-assistant procore live records count --project tropical --endpoint rfis --json
hb-assistant procore live records count --project tropical --endpoint rfi-responses --json
```

Re-running the same apply does **not** duplicate rows — the upsert key
includes `(project_key, endpoint_id, parent_procore_id, procore_record_id)`.

Latest apply evidence: `docs/evidence/construction-intelligence-phase-04a/04-rfi-live-sync.md`.

Note: `rfi-responses` remains `live_verified=False` in the registry. Its
records are populated only as a byproduct of the rfis parent fetch — direct
CLI invocation of `procore live sync --endpoint rfi-responses` correctly
returns `state="not_live_verified"` because no parent rfi id is supplied.

## Phase 04A Prompt 05: Submittal live apply

The submittal family mirrors the RFI N+1 pattern. Apply submittals (and
their responses, when the path resolves) to local SQLite:

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical \
  --endpoint submittals \
  --apply --sqlite-only \
  --max-pages 3 --max-items 100 \
  --confirm-live-get --json
```

The orchestrator issues one GET to `/rest/v1.0/projects/{id}/submittals`
for the parent list, then issues one GET per parent at
`/rest/v1.0/projects/{id}/submittals/{submittal_id}/responses`. Responses
persist as rows with `endpoint_id="submittal-responses"` and
`parent_procore_id=<submittal_id>` set. Child fetch is capped internally
at `max_pages=1, max_items=50` per parent. A 4xx on one child fetch
increments `child_errors_count` and continues to the next parent — the
run is not aborted. Receipt fields match the RFI family:
`parent_*` and `child_*` counters plus `child_endpoint_id`.

Verify persistence:

```bash
hb-assistant procore live records count --project tropical --endpoint submittals --json
hb-assistant procore live records count --project tropical --endpoint submittal-responses --json
hb-assistant procore live records count --project tropical --endpoint submittal-packages --json
```

Re-running the same apply does **not** duplicate rows — the upsert key
includes `(project_key, endpoint_id, parent_procore_id, procore_record_id)`.

Latest apply evidence: `docs/evidence/construction-intelligence-phase-04a/05-submittal-live-sync.md`.

**Known contract drift (Prompt 05 backlog).** Against `tropical`,
`/rest/v1.0/projects/{project_id}/submittals/{submittal_id}/responses`
and `/rest/v1.0/projects/{project_id}/submittals/packages` both return
HTTP 404. The orchestrator fails closed cleanly per fetch (structured
`child_transport_error` / `transport_error` receipts; no abort). Both
endpoints stay `live_verified=False` until a follow-up prompt verifies
the correct Procore paths (mirrors the `meetings` 404 disposition).

## Phase 04A Prompt 06: Observation live apply

The `observations` endpoint (a parent-only top-level surface, no N+1)
is promoted to `live_verified=True`. Live smoke and three live applies
(caps 1/5, 3/100, 3/100 re-run) succeeded against `tropical`.

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical \
  --endpoint observations \
  --apply --sqlite-only \
  --max-pages 3 --max-items 100 \
  --confirm-live-get --json
```

Review routing is heuristic-driven via
`normalize_observation._safety_route_decision()` — a four-field scan
of status / type / subtype / title / description for safety, incident,
injury, near-miss, corrective-action, unsafe, violation, PPE, and
personnel fragments. Any hit sets `review_required=true` and
`safety_route=true`; a no-fragment row with no assignee sets
`review_required=true` with `routing_reason="assignee_missing"`; only a
benign row with an assignee present falls to `routing_reason="default_low_risk"`.
Descriptions are never persisted as raw text — they're reduced to a
SHA-256 hash-only `description_summary`; the `redacted_excerpt` is
derived from the title only (truncated to 200 chars).

Verify persistence:

```bash
hb-assistant procore live records count --project tropical --endpoint observations --json
```

Re-running the same apply does **not** duplicate rows — the upsert key
includes `(project_key, endpoint_id, parent_procore_id, procore_record_id)`.

In the `tropical` live data set, all 100 observations sampled were
closed without an `assignee_id` populated, so every row routed via the
`assignee_missing` fallback (`review_required=1`). Unit tests continue
to cover all three heuristic paths (safety, default_low_risk,
assignee_missing) on synthetic fixtures.

Latest apply evidence: `docs/evidence/construction-intelligence-phase-04a/06-observation-live-sync.md`.

## Phase 04A Prompt 07: Meeting live sync (deferred on schema mismatch)

The Phase 04A orchestrator now ships the `meetings → meeting-topics` N+1
child dispatch (third hard-coded branch alongside `rfis` and
`submittals`). When promoted, the operator command will be:

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical \
  --endpoint meetings \
  --apply --sqlite-only \
  --max-pages 3 --max-items 100 \
  --confirm-live-get --json
```

The orchestrator issues one GET to
`/rest/v1.1/projects/{project_id}/meetings` (Prompt 07 path discovery)
for parents, then issues one GET per parent at
`/rest/v1.0/projects/{project_id}/meetings/{meeting_id}/topics`. Topics
persist with `endpoint_id="meeting-topics"`,
`parent_procore_id=<meeting_id>`, `review_required=True`, and
description/action_items reduced to SHA-256 hash-only summaries — never
raw text.

**Prompt 07 disposition: deferred.** Five candidate Procore paths were
probed against tropical:

| Path                                                                  | HTTP | Records | Note                                  |
| ---                                                                   | ---  | ---     | ---                                   |
| `/rest/v1.0/projects/{project_id}/meetings`                           | 404  | 0       | original adapter path                 |
| `/rest/v1.1/projects/{project_id}/meetings`                           | 200  | 10      | **path resolves**; v1.0 normalizer mismatch |
| `/rest/v2.0/companies/5280/projects/{project_id}/meetings`            | 200  | 1       | v1.0 normalizer mismatch              |
| `/rest/v1.0/companies/5280/meetings`                                  | 404  | 0       | invalid surface                       |
| `/rest/v1.0/projects/{project_id}/project_meetings`                   | 404  | 0       | invalid noun                          |

The v1.1 path is preserved as the adapter's `path_template` so a future
prompt that updates `normalize_meeting` for the v1.1 payload shape can
promote without re-probing. `meetings` and `meeting-topics` both stay
`live_verified=False` until that follow-up.

Latest evidence: `docs/evidence/construction-intelligence-phase-04a/07-meeting-live-sync.md`.

## Phase 04A Prompt 08: Selected daily-log live sync

Prompt 08 extends the daily-log family from `daily-log-weather` alone
to five verified per-section endpoints plus the demoted `daily-log-dcrs`
backlog entry. The canonical registry grows from 14 to 16 rows.

| Section                           | Live verified | review_required | safety_route | Hash-only body |
| ---                               | ---           | ---             | ---          | ---            |
| `daily-log-weather`               | ✓ (Prompt 03) | False           | False        | —              |
| `daily-log-manpower`              | ✓             | False           | False        | —              |
| `daily-log-deliveries`            | ✓             | False           | False        | —              |
| `daily-log-inspections` (new)     | ✓             | False           | False        | comments / description |
| `daily-log-notes`                 | ✓             | **True**        | False        | note / body / comments |
| `daily-log-delays-review-routed`  | ✓             | **True**        | **True**     | description / cause / safety_violation |
| `daily-log-dcrs` (new)            | ✗ (HTTP 404)  | n/a             | n/a          | n/a            |

Operator command (per section):

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical \
  --endpoint daily-log-<section> \
  --apply --sqlite-only \
  --max-pages 3 --max-items 100 \
  --confirm-live-get --json
```

Each promoted section ran two `live_apply` runs in Prompt 08 (apply +
re-run at the same caps). All ten apply runs returned `state=success`
with `retrieved_count=0` (the `tropical` project carries no live data
in these sections at the time of execution); the chain — gate →
transport → paginate → normalize → upsert → records count — is proven
end-to-end against an empty result set, with `sync_run_id` audit rows
recorded for each invocation.

**Free-text guarantees.** The `notes` and `delays-review-routed`
endpoints reduce any incoming free-text field (`note`, `body`,
`comments`, `description`, `cause`, `safety_violation`) to a SHA-256
`*_summary` structure (`type`, `length`, `hash_prefix`) — raw text is
never persisted. Unit tests in
`tests/test_procore_live_sync_verified_chain.py` assert the invariant
against a synthetic secret marker.

**Backlog: `daily-log-dcrs`.** The Daily Construction Report path
`/rest/v1.0/projects/{project_id}/dcrs` returned HTTP 404 against
`tropical`. The adapter row carries the failure receipt id in
`verification_reason`; promotion deferred pending Procore docs
investigation.

Latest evidence: `docs/evidence/construction-intelligence-phase-04a/08-selected-daily-log-live-sync.md`.

## Phase 04A backlog resolution: submittal-responses / submittal-packages

The Prompt 05 backlog has been partially resolved:

- **`submittal-packages`** — RESOLVED. The Procore path uses the
  underscored noun: `/rest/v1.0/projects/{project_id}/submittal_packages`
  (NOT the previously-tried `/submittals/packages`). Promoted to
  `live_verified=True`; `verification_reason="live_smoke_passed_2026-05-28:7b9077ee"`.

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical \
  --endpoint submittal-packages \
  --apply --sqlite-only \
  --max-pages 3 --max-items 100 \
  --confirm-live-get --json
```

- **`submittal-responses`** — DEFERRED. Four candidate child paths were
  probed against tropical (`/v1.0/responses`, `/v1.0/approvers`,
  `/v1.0/reviews`, `/v1.1/approvers`, `/v1.1/responses`); all returned
  HTTP 404. The adapter's `verification_reason` records the full probe
  matrix:
  `phase_04a_backlog_2026-05-28:probed_v1.0_responses_v1.0_approvers_v1.0_reviews_v1.1_approvers_v1.1_responses_all_404`.
  The orchestrator's `elif fetch_submittal_responses` dispatch is
  preserved (unit-tested) for future activation once the correct
  Procore child surface is identified.

Latest evidence: `docs/evidence/construction-intelligence-phase-04a/09-submittal-backlog-resolution.md`.

## Phase 04A backlog resolution: meetings v1.1 normalizer

The Prompt 07 meetings backlog is RESOLVED. `meetings` now executes the
full live chain at the v1.1 path with the grouped payload correctly
flattened to per-meeting rows.

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical \
  --endpoint meetings \
  --apply --sqlite-only \
  --max-pages 3 --max-items 100 \
  --confirm-live-get --json
```

What changed:

1. **Orchestrator flatten.** Procore's v1.1 meetings endpoint returns
   grouped responses: `[{"group_title": "...", "meetings": [...]}, ...]`.
   `live_sync.py` now unwraps the `meetings` arrays from each group
   before normalization, honoring `--max-items` at the meeting-row level
   (not the group level). v1.0 (flat list) passes through unchanged.

2. **Normalizer extended.** `normalize_meeting` carries both v1.0 and
   v1.1 canonical field names — `start_time` / `starts_at`,
   `end_time` / `ends_at`, `organizer_id` / `created_by_id`, plus the
   new `meeting_topics_count`. The metadata-only contract is preserved:
   `description` (free-text in v1.1) is NOT whitelisted; raw text never
   persisted.

Tropical results: live apply at caps `--max-pages 3 --max-items 100`
returned `state=partial_success` with 96 parent meeting rows persisted;
re-run at the same caps is idempotent (96 → 96 under the upsert PK).

**Topics backlog persists.** `meeting-topics` was probed at both v1.0
and v1.1 child paths during the parent apply. v1.0 returned HTTP 404 on
every parent; v1.1 returned a mix of HTTP 404 and HTTP 429 (rate-limit),
so per the stop conditions the probe was aborted. `meeting-topics` stays
`live_verified=False` with `verification_reason="phase_04a_backlog_2026-05-28:probed_v1.0_topics_v1.1_topics_mixed_http_404_and_429_rate_limit"`.
The orchestrator's N+1 dispatch is preserved (unit-tested) for future
activation.

Latest evidence: `docs/evidence/construction-intelligence-phase-04a/10-meetings-v1.1-normalizer-resolution.md`.

## Phase 04A backlog resolution: remaining `_UNVERIFIED_IDS` + N+1 architecture pivot

The orchestrator's N+1 child GET pattern (one HTTP call per parent for
replies / responses / topics) was burning Procore's rate-limit budget
unnecessarily. Procore's RFI and submittal list payloads already embed
their children inline, so the orchestrator now extracts children from
the parent payload rather than issuing per-parent GETs.

What changed:

1. **Generic child-adapter dispatch.** `live_sync.py` no longer has
   hard-coded `if/elif` branches for rfis / submittals / meetings. A
   single helper `_resolve_child_adapter(parent)` scans the registry by
   `family` + `parent_record_id_field`, and `_CHILD_NORMALIZER_BY_ID`
   resolves the normalizer.

2. **Inline child extraction.** A small map
   `_INLINE_CHILD_FIELD_BY_PARENT_ID = {"rfis": "replies", "submittals":
   "responses", "meetings": "topics"}` tells the orchestrator which
   field to read on each parent record. Children are normalized and
   upserted with `parent_procore_id` set. Zero additional HTTP calls
   are issued for children.

3. **Promotions.** `rfi-responses` and `submittal-responses` are now
   `live_verified=True`. They populate inline whenever the parent apply
   runs against a project that has actual responses.

4. **Standardized normalizer kwargs.** All three child normalizers
   (`normalize_rfi_reply`, `normalize_submittal_response`,
   `normalize_meeting_topic`) accept a uniform `parent_procore_id`
   kwarg. Internal data-key names (`parent_rfi_stable_key`,
   `parent_submittal_stable_key`, `parent_meeting_id`) are preserved
   for backward compatibility with downstream consumers.

Remaining deferrals:

- `meeting-topics` — the Procore v1.1 meetings parent payload does NOT
  embed topics (only `meeting_topics_count` per the Prompt 07
  discovery probe). Promotion requires either a working per-meeting
  `/topics` GET surface (prior probes returned 404 + 429) or an
  embedded topics array in the parent payload (Procore design choice).
- `daily-log-dcrs` — top-level endpoint at `/dcrs` still returns 404.
  Multi-path probing was deferred under the active Procore rate-limit
  budget.

Latest evidence: `docs/evidence/construction-intelligence-phase-04a/11-unverified-ids-resolution.md`.

## Phase 04A final closeout: 16/16 endpoints verified

The operator supplied exact Procore-docs path snippets for the last two
deferred endpoints. Both promote to `live_verified=True` end-to-end
against `tropical`.

- **`daily-log-dcrs`** at `/rest/v1.0/projects/{project_id}/daily_construction_report_logs`
  (the prior `/dcrs` 404 was the wrong path; the underscored verbose
  resource name is correct). Schema covers labor-hour fields,
  vendor/trade/location nested objects, and a `notes` free-text field
  reduced to a SHA-256 `notes_summary`.

- **`meeting-topics`** at `/rest/v1.1/projects/{project_id}/meeting_topics`
  (standalone v1.1 root noun — NOT nested under
  `/meetings/{id}/topics`). The adapter was refactored from a meetings
  child to a standalone top-level endpoint. `minutes` free-text content
  is reduced to a SHA-256 `minutes_summary`. **Operational caveat:**
  Procore's server returns HTTP 500 at `per_page=100`; operators should
  use `--max-items <= 10` for this endpoint.

Final verified set: **16 of 16** canonical endpoints. `_UNVERIFIED_IDS`
parametrized test count: 0.

Operator commands:

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint daily-log-dcrs \
  --apply --sqlite-only --max-pages 3 --max-items 100 \
  --confirm-live-get --json

HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint meeting-topics \
  --apply --sqlite-only --max-pages 1 --max-items 10 \
  --confirm-live-get --json
```

Latest evidence: `docs/evidence/construction-intelligence-phase-04a/12-final-unverified-resolution.md`.

## Phase 04A: meeting-detail endpoint (rich per-meeting fetch)

The `meeting-detail` endpoint (registry row #17) provides a rich
per-meeting view from Procore's v1.1 detail surface
(`/rest/v1.1/projects/{project_id}/meetings/{id}`). The detail payload
embeds attendees (PII), full topics with `minutes` (HTML body),
categories, and conclusion. All PII reduces to SHA-256 hash-only
summaries; all free-text bodies reduce to `*_summary` hash structures;
the `remote_meeting_url` is path-only with query strings stripped.

Operator command:

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical \
  --endpoint meeting-detail \
  --apply --sqlite-only \
  --max-pages 1 --max-items 5 \
  --confirm-live-get --json
```

Dispatch shape: the orchestrator first fetches the meetings list at
`parent_path_template` (one HTTP call), then issues **one detail GET
per meeting** in the returned list (N+1, bounded by `--max-items`).
Each detail payload becomes one `meeting-detail` row plus N topic rows
extracted from `meeting_categories[].meeting_topic[]` and upserted
under `endpoint_id="meeting-topics"` with `parent_procore_id` pointing
back to the meeting.

Cost model: at `--max-items N`, the orchestrator issues `1 + N` HTTP
calls. Each parent meeting yields one meeting-detail row and (in
tropical observation) ~20 meeting-topics rows. The operator-acknowledged
N+1 trade-off enables the rich data; the prior caveats about Procore
rate limits apply — pick `--max-items` conservatively until the apply
proves stable for the project.

PII guarantees:
- `attendees[].login_information.login` (email) → SHA-256
  `hash_prefix` only.
- `attendees[].login_information.name` → never persisted.
- `attendees[].id` (numeric) preserved as `attendee_id` (opaque
  Procore identifier, not PII by itself).
- `meeting_topic[].assignments[]` → same hashed-summary treatment via
  `_assignments_summary`.
- `description`, `conclusion`, topic `minutes` → SHA-256 `*_summary`
  structures.
- `remote_meeting_url` → path-only, query strings stripped (Zoom/Teams
  join tokens never persist).

Latest evidence: `docs/evidence/construction-intelligence-phase-04a/13-meeting-detail-endpoint.md`.

## Phase 04A: punch-items endpoint

The `punch-items` endpoint (registry row #18) provides Procore's
v1.1 punch items list at `/rest/v1.1/punch_items`. It is the first
Phase 04A endpoint where `project_id` is a **query parameter** rather
than a path placeholder — the orchestrator's existing
`params={"project_id": ...} if "{project_id}" not in path else None`
branch handles this automatically. No code change to the orchestrator's
dispatch was needed.

Operator command:

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical \
  --endpoint punch-items \
  --apply --sqlite-only \
  --max-pages 3 --max-items 100 \
  --confirm-live-get --json
```

PII guarantees:
- People refs (`ball_in_court`, `created_by`, `closed_by`,
  `punch_item_manager`, `final_approver`, `assignees`,
  `assignments[].login_information`) reduce to
  `{count, hashed_identifiers: [{hash_prefix, id}, …]}`. The
  `hash_prefix` is the SHA-256 prefix of the `login` email when
  present, otherwise of the `name`. Numeric `id` is preserved as an
  opaque Procore identifier.
- Free-text bodies (`description`, `schedule_risk_reason`,
  `assignments[].comment`) reduce to SHA-256 `*_summary` structures.
- Structured risk + financial signals (`cost_impact`,
  `cost_impact_amount`, `schedule_impact`, `schedule_impact_days`,
  `schedule_risk`, `schedule_risk_confidence`,
  `schedule_risk_probability`) preserved verbatim for operator triage.
- Variable-shape `custom_fields` preserved structurally:
  decimal/boolean/lov_entry values verbatim, string values reduced to
  hash-only summaries.
- All persisted rows carry `review_required=1` (PII-bearing by design).

Latest evidence: `docs/evidence/construction-intelligence-phase-04a/14-punch-items-endpoint.md`.

## Phase 04A: schedules + activities endpoints (v2.0 company-scoped)

Two new endpoints from Procore's v2.0 surface:
- `schedules` — `/rest/v2.0/companies/{company_id}/projects/{project_id}/schedules`
- `activities` — per-schedule child fetched via N+1 from the schedules list.

Both endpoints return `{"data": [...]}` envelopes; the shared
`http_client.paginate` now unwraps both `items` and `data` keys.
`_resolve_path` now substitutes `{company_id}` from the existing
`COMPANY_ID = "5280"` constant alongside `{project_id}`.

Operator commands:

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint schedules \
  --apply --sqlite-only --max-pages 3 --max-items 100 \
  --confirm-live-get --json

HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint activities \
  --apply --sqlite-only --max-pages 1 --max-items 5 \
  --confirm-live-get --json
```

Dispatch shape:
- `schedules`: single list call. Operational scheduling data —
  `review_required=False`.
- `activities`: list-fetch (1 call to the schedules list at
  parent_path_template) + N+1 (one activities GET per schedule, bounded
  by `--max-items`). Each activity row carries
  `parent_procore_id = schedule_id` so operators can join activities
  back to their parent schedule.

Free-text guarantee: activity `notes` reduces to a SHA-256
`notes_summary`; raw text never persists. Structured fields
(`category_data`, `resource_data`, `assigned_company`, risk + duration
fields) preserved verbatim.

Latest evidence: `docs/evidence/construction-intelligence-phase-04a/15-schedules-and-activities-endpoints.md`.

## Inspections + Inspection-Items (2026-05-29)

Inspections is a v1.0 list endpoint at
`/rest/v1.0/projects/{project_id}/checklist/lists` returning checklist
instances. inspection-items is the per-list child fetched via the same
list+N+1 dispatch pattern as activities. As of 2026-05-29 the parent
endpoint is live-verified; the child endpoint is registered but
fail-closed pending operator confirmation of the canonical list-items
path (Procore returned 404 against the two most plausible variants; the
operator detail URL requires `section_id`, implying a list-by-section
endpoint that has not yet been identified — flip
`endpoints.py::inspection-items.live_verified` to True once the path is
known).

Operator commands:

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live smoke \
  --project tropical --endpoint inspections --confirm-live-get --json
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint inspections \
  --apply --sqlite-only --max-pages 3 --max-items 100 \
  --confirm-live-get --json
```

Redaction posture:
- Inspections — `review_required` heuristic on safety inspection_type /
  overdue / open status. PII (created_by, closed_by, point_of_contact,
  responsible_contractor, inspectors, distribution_members) hashed via
  `person_hash_summary`. Signature requests + attachments reduced to
  count + hashed filename + path-only URL. `description` hashed.
  Custom fields preserve numeric/boolean/lov_entry values verbatim;
  string values hashed.
- Inspection-items — always `review_required=True`. observations,
  comments, histories, attachment_histories, attachments all reduced to
  `*_summary` blocks with hashed identifiers + hashed bodies.

`procore obsidian register` rejects `--endpoint inspections` and
`--endpoint inspection-items` with the existing `unsupported_endpoint`
error (no register template exists for the inspections family yet —
future work).

Latest evidence: `docs/evidence/construction-intelligence-phase-04a/20-inspections-and-inspection-items.md`.

## Inspection-sections bridge + 2-level inspection-items dispatch (2026-05-29)

The Procore checklist model is `Inspection (list) → Section → Item`.
The `inspection-sections` endpoint is the bridge; `inspection-items`
walks all three layers in a single 2-level dispatch (sections marked
`not_applicable=True` are skipped to save requests).

As of 2026-05-29 both endpoints are **registered but fail-closed**:
both list-of-sections path variants returned 404 against tropical, and
items can't be reached without a verified sections path. The structural
infrastructure (normalizer, 2-level dispatch, chain tests) is in place;
flipping `endpoints.py::inspection-sections.live_verified` to True and
correcting its `path_template` is the only change needed once the
operator confirms the canonical Procore list-of-sections URL. After
that, `inspection-items` follows automatically.

Operator commands once paths are confirmed:

```bash
HB_PROCORE_LIVE=1 hb-assistant procore live smoke \
  --project tropical --endpoint inspection-sections --confirm-live-get --json
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint inspection-sections \
  --apply --sqlite-only --max-pages 3 --max-items 100 \
  --confirm-live-get --json

# Items follow once sections are verified — 2-level dispatch cost is
# roughly 1 + N (inspections) + N×M (sections per inspection × items per
# section). Cap --max-items conservatively for large projects.
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint inspection-items \
  --apply --sqlite-only --max-pages 1 --max-items 5 \
  --confirm-live-get --json
```

Latest evidence: `docs/evidence/construction-intelligence-phase-04a/21-inspection-sections-bridge.md`.

## Inspection-sections + inspection-items flat-list re-target (2026-05-29)

The canonical Procore endpoints are flat project-scoped paginated lists,
NOT per-inspection N+1 fetches. Both endpoints are live-verified as of
2026-05-29.

```bash
# Inspection-sections (v1.0 flat list)
HB_PROCORE_LIVE=1 hb-assistant procore live smoke \
  --project tropical --endpoint inspection-sections --confirm-live-get --json
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint inspection-sections \
  --apply --sqlite-only --max-pages 3 --max-items 100 \
  --confirm-live-get --json

# Inspection-items (v1.1 flat list; each item payload carries list_id +
# section_id directly so parent_procore_id derives at upsert)
HB_PROCORE_LIVE=1 hb-assistant procore live smoke \
  --project tropical --endpoint inspection-items --confirm-live-get --json
HB_PROCORE_LIVE=1 hb-assistant procore live sync \
  --project tropical --endpoint inspection-items \
  --apply --sqlite-only --max-pages 3 --max-items 100 \
  --confirm-live-get --json
```

Redaction posture (unchanged from prior runbook section):
- Inspection-sections — no PII, no free-text bodies, no hashing.
- Inspection-items — `review_required=True`. PII (responder, assignee,
  created_by) hashed via `person_hash_summary`; free-text (`details`,
  `company_template_item_details`, `item_response.payload.text_value`,
  `comments[].body`, `histories[].body`) hashed via `hash_summary`;
  attachments URL → path-only + hashed filename.

Latest evidence: `docs/evidence/construction-intelligence-phase-04a/22-inspection-flat-list-endpoints.md`.

## Obsidian register from Phase 04A live SQLite (Prompt 09A)

A read-only projection of `procore_live_records` into per-family Obsidian
register sections. Never calls Procore; consumes whatever has already been
persisted by `procore live sync`.

Operator commands:

```bash
# Preview the section for one endpoint family (zero side effects).
hb-assistant procore obsidian register \
  --project tropical --endpoint rfis --from-sqlite --dry-run --json

# Write the marker-bounded section into the local vault.
hb-assistant procore obsidian register \
  --project tropical --endpoint rfis --from-sqlite --apply --confirm --json
```

The command requires `--from-sqlite` (explicit no-live-call assertion). The
`--apply --confirm` gate matches the rest of the Procore CLI: non-TTY without
`--confirm` exits `1`; TTY without `--confirm` prompts. Apply writes to
`$HB_CONSTRUCTION_VAULT_ROOT/01_Projects/<project_key>.procore-<family>-register.md`
using the same marker-bounded region as `procore obsidian preview`, so reruns
are byte-identical and the two commands interoperate cleanly on the same files.

Supported endpoints:

| Endpoint id | Renders into |
| --- | --- |
| `rfis`, `rfi-responses` | `procore-rfi-register.md` (RFI table) |
| `submittals`, `submittal-responses`, `submittal-packages` | `procore-submittal-register.md` |
| `observations` | `procore-observation-register.md` |
| `meetings`, `meeting-detail` | `procore-meeting-register.md` (Meetings section) |
| `meeting-topics` | `procore-meeting-register.md` (Topics section) |
| `daily-log-weather`, `daily-log-manpower`, `daily-log-notes` | `procore-daily-log-index.md` |

Unsupported endpoints (`projects`, `punch-items`, `schedules`, `activities`)
return `ok=False`, `status="unsupported_endpoint"`, exit code `2`, and a
`next_steps` hint pointing at `procore obsidian preview` for the foundational
`project_card` / `endpoint_audit` projections. Adding register templates for
these families is future work.

Rows with `review_required=1` (PII routing, sensitive_reason from the live
sync) are excluded from the register table and surfaced under `review_items`
in the JSON envelope.

Latest evidence: `docs/evidence/construction-intelligence-phase-04a/16-obsidian-register-from-live-records.md`.

## Rollback (Prompt 11)

Two operator-supported rollback paths. Both run entirely against the local
SQLite at `~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`;
neither calls Procore.

### Rollback by receipt id (sync_run_id)

Removes every `procore_live_records` row attributed to one sync run while
preserving the matching `procore_live_sync_runs` row (audit trail of the
rolled-back run remains discoverable via `procore live records count` and
the JSON sync receipts).

```bash
# Dry-run preview (default; mutates nothing). Replace RUN_ID with the
# sync_run_id from the apply receipt you want to roll back.
python -c "
from hb_assistant.store.procore_repositories import delete_procore_live_records_by_sync_run
print(delete_procore_live_records_by_sync_run(sync_run_id='RUN_ID', dry_run=True))
"

# Apply the rollback (only after reviewing the would_delete count above).
python -c "
from hb_assistant.store.procore_repositories import delete_procore_live_records_by_sync_run
print(delete_procore_live_records_by_sync_run(sync_run_id='RUN_ID', dry_run=False))
"
```

The dry-run preview returns `{sync_run_id, would_delete, dry_run: True}`;
the apply form returns `{sync_run_id, deleted, dry_run: False}`. A second
apply for the same run-id is itself idempotent — it returns
`{deleted: 0, ...}`.

### Rollback by backup restore

Take a WAL-safe SQLite snapshot before any high-risk apply; restore it
afterward if the apply produced unwanted state. Uses the `sqlite3` shell's
`.backup` command, which copies the database in a consistent way
regardless of WAL state — `shutil.copyfile` is NOT WAL-safe and will miss
in-flight pages.

```bash
DB="$HOME/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"
BACKUP="$DB.bak.$(date +%Y%m%d%H%M%S)"

# Take a snapshot (before the apply).
sqlite3 "$DB" ".backup '$BACKUP'"

# ...run an apply that you may want to roll back...

# Restore the snapshot (reverses every change since the snapshot).
sqlite3 "$DB" ".restore '$BACKUP'"
```

Latest evidence: `docs/evidence/construction-intelligence-phase-04a/18-idempotency-reconciliation-rollback.md`.

## References

- Source-of-truth evidence: `docs/evidence/construction-intelligence-phase-03/`
  (prompts 00–12; 09/10/11/12 are the most relevant for current operations).
- Sibling runbook: `docs/operations/construction-agent-operator-runbook.md`.
- Local-runtime guide: `docs/operations/mvp-local-runtime-operator-guide.md`.
- Seeds: `resources/config/procore_endpoint_contract.seed.yaml`,
  `resources/config/procore_projects.seed.yaml`,
  `resources/config/procore_sensitive_routing_rules.yaml`.
- Architecture index: `docs/architecture/00-README.md`.
