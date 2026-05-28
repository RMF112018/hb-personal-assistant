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

# EXPLICIT opt-in apply. Writes normalized rows to LOCAL SQLite only
# after the Prompt 07 audit gate passes. Never mutates Procore.
hb-assistant procore sync run --project tropical --apply --confirm --json
```

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
