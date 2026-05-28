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

## References

- Source-of-truth evidence: `docs/evidence/construction-intelligence-phase-03/`
  (prompts 00–12; 09/10/11/12 are the most relevant for current operations).
- Sibling runbook: `docs/operations/construction-agent-operator-runbook.md`.
- Local-runtime guide: `docs/operations/mvp-local-runtime-operator-guide.md`.
- Seeds: `resources/config/procore_endpoint_contract.seed.yaml`,
  `resources/config/procore_projects.seed.yaml`,
  `resources/config/procore_sensitive_routing_rules.yaml`.
- Architecture index: `docs/architecture/00-README.md`.
