# Construction-Agent Operator Runbook

Authoritative operator surface for the `hb-assistant construction-agent`
CLI. Every command honors `--json` (the default). Every command is either
read-only or gated behind an explicit `--apply` flag.

**Governance:** SQLite is authoritative for sync state. Markdown vault
output is a recomputable projection. External systems (SharePoint,
OneDrive, Procore, Outlook) are **read-only** and never written. The
deterministic controller policy at
`resources/config/review_required_rules.seed.yaml` overrides any model
recommendation.

## Environment variables

| Var | Purpose | Set when |
| --- | --- | --- |
| `HB_CONSTRUCTION_VAULT_ROOT` | Required for `vault preview --apply` and `sync --apply` | Operator wants Markdown projections written to disk |
| `HB_CONSTRUCTION_SOURCES` | Override path to source-registry YAML | Testing or overriding the seeded registry |
| `HB_CONSTRUCTION_REVIEW_RULES` | Override path to review-rules YAML | Testing or overriding the controller policy |
| `HB_CONSTRUCTION_MODEL_ROUTING` | Override path to Ollama routing YAML | Testing or overriding the model routing config |

When a variable is unset, the seeded file under `resources/config/` wins,
with an optional repo-local override at `config/<name>.yml` taking
precedence over the seed.

## Lifecycle

### 1. Bootstrap

```bash
# Validate the seeded registry + rules + routing in one call.
hb-assistant construction-agent validate --json

# Inspect or list registered sources.
hb-assistant construction-agent sources list --json
hb-assistant construction-agent sources validate --json

# Create the construction-vault subdirectory layout (apply requires
# HB_CONSTRUCTION_VAULT_ROOT).
hb-assistant construction-agent vault bootstrap --dry-run --json
HB_CONSTRUCTION_VAULT_ROOT="$VAULT" hb-assistant construction-agent vault bootstrap --apply --json
```

### 2. Resolve sources to Graph IDs

```bash
# Check delegated MSAL cache (no live call).
hb-assistant construction-agent graph auth status --json

# Resolve sites/drives to canonical IDs (apply persists to SQLite).
hb-assistant construction-agent graph sources resolve --dry-run --json
hb-assistant construction-agent graph sources resolve --apply --json
```

### 3. Crawl + sync

```bash
# Read-only delta crawl per source. Apply writes inventory + delta token
# to SQLite only (never to the external system).
hb-assistant construction-agent graph delta --source tropical-sharepoint --dry-run --json
hb-assistant construction-agent graph delta --source tropical-sharepoint --apply --json

# Build source manifests + sync receipts + processing receipt. Apply
# writes Markdown to the construction vault.
hb-assistant construction-agent sync --dry-run --json
HB_CONSTRUCTION_VAULT_ROOT="$VAULT" hb-assistant construction-agent sync --apply --json
```

### 4. Triage

```bash
# Apply the deterministic controller policy across inventory; apply
# enqueues matches into the review queue (SQLite only).
hb-assistant construction-agent review evaluate --dry-run --json
hb-assistant construction-agent review evaluate --apply --json

# Inspect open review-required items.
hb-assistant construction-agent review list --status open --json

# Run the Ollama classifier on a built-in offline fixture set.
hb-assistant construction-agent classify run --fixture sample --json

# Or feed a known raw model output for a specific item (offline; bypasses
# the live Ollama call). Live mode is intentionally CLI-gated.
hb-assistant construction-agent classify run \
  --source tropical-sharepoint --item ITEM_ID \
  --mock-output '{"item_id":"ITEM_ID","proposed_label":"operational","confidence":0.9,"rationale":"...","risk_terms":[]}' \
  --json

# Inspect the model-decisions audit trail.
hb-assistant construction-agent classify decisions --status review --json
```

### 5. Inspect

```bash
# Single read-only dashboard joining schema version, per-source state,
# queue counts, decision counts, and rule-set versions.
hb-assistant construction-agent index status --json

# Filter the dashboard to one source.
hb-assistant construction-agent index status --source tropical-sharepoint --json

# Re-render the vault projection from current SQLite state (apply
# requires HB_CONSTRUCTION_VAULT_ROOT). Idempotent.
HB_CONSTRUCTION_VAULT_ROOT="$VAULT" hb-assistant construction-agent vault preview --apply --json
```

## Command summary

| Group | Command | Side effects |
| --- | --- | --- |
| `sources` | `list`, `validate` | none (read-only) |
| `graph` | `auth status`, `sources resolve`, `delta` | SQLite when `--apply`; never external writes |
| `sync` | `sync` | Vault Markdown when `--apply` + env var set |
| `vault` | `bootstrap`, `preview` | Vault Markdown when `--apply` + env var set |
| `review` | `evaluate`, `list` | SQLite when `--apply` |
| `classify` | `run`, `decisions` | SQLite (audit row) when run with `--fixture` or `--mock-output` |
| `index` | `status` | none (read-only) |
| `validate` | (top-level) | none (read-only; applies idempotent migration as a side effect) |

## Dry-run / apply convention

- Every potentially-mutating command defaults to `--dry-run`. `--apply`
  is the only path that writes state.
- SQLite writes are local-only and reversible (delete `~/Library/Application Support/HB Personal Assistant/db/*.sqlite` to reset).
- Vault writes are atomic (tempfile + `os.replace`) and marker-bounded.
- External systems are never written to. There is no `--apply` path that
  reaches SharePoint, OneDrive, Procore, or Outlook.

## Recovery

- If schema is stale, any `construction-agent` command will idempotently
  apply pending migrations. `construction-agent validate --json` is the
  canonical health check.
- If the source registry is unloadable, the CLI fails fast with
  `status: "source_registry_unavailable"` and a structured payload — no
  partial state is written.
- If Ollama is unreachable, the classifier surfaces a sanitized
  `OllamaUnavailable` error and persists nothing. The deterministic
  controller policy continues to operate independently.
