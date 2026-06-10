# Procore Endpoint Structured Analytics Foundation + Daily-Brief Usefulness Package

## Objective

Implement a durable, local, analytics-grade Procore endpoint data foundation for `RMF112018/hb-personal-assistant`.

The primary outcome is not a better daily brief by itself. The primary outcome is that Procore endpoint data is captured and persisted locally in structured, endpoint-appropriate tables that can support future analytics, reporting, reprocessing, local retrieval, source-linked reasoning, and operator drill-down.

The daily brief and local model are downstream consumers. They must consume ranked/redacted projections from the structured data foundation; they must not define or constrain the raw/structured storage layer.

## Repository

- GitHub: `RMF112018/hb-personal-assistant`
- Local path: `/Users/bobbyfetting/hb-personal-assistant`
- Package path: `docs/planning/procore_endpoint_structured_analytics_foundation_package/README.md`
- Evidence path: `docs/evidence/procore_endpoint_structured_analytics_foundation/`

## Supersedes

This package supersedes the daily-brief-centered package at:

`docs/planning/procore_endpoint_raw_content_and_daily_brief_usefulness_package/`

That package correctly identified raw-content and ranking gaps, but its framing was too narrow. This package reframes the work as a Procore structured analytics foundation, with daily brief usefulness as one downstream validation target.

## Critical product requirement

Raw Procore endpoint data must not be reduced to only:

- aggregate counts,
- action signals,
- redacted summaries,
- generic opaque JSON blobs,
- local-model context packets,
- daily-brief candidate rows.

The implementation must persist endpoint business content in structured, queryable, endpoint-family tables. A governed raw-payload landing table is still required for replay/reprocessing, but it is not sufficient by itself.

## Source DB audit findings to carry forward

The provided DB audit package found:

- Schema version `45`.
- `30,059` Procore live records.
- `27,963` Procore snapshots.
- `29,738` Procore change events.
- `85,525` Procore financial amount facts.
- `5,866` Procore action signals.
- `0` `daily_brief_action_candidates`.
- `0` `candidate_source_refs`.
- `117` `calendar_event_raw_content` rows.
- `1` `email_message_raw_content` row.
- No equivalent Procore raw-content structured storage family.
- Procore daily-brief usefulness classified as `blocked_by_ranking`.
- Current Procore signal volume is dominated by stale/aggregate sludge and lacks due-soon/actionable selection.

Treat those findings as a starting point. Repo truth and a fresh local DB-copy audit are authoritative.

## Hard constraints

The local agent must obey these constraints throughout:

- Do not modify `main` directly.
- Do not merge or rebase unless explicitly instructed after final handoff.
- Do not mutate the production DB during audit or validation.
- Use timestamped `/tmp` SQLite `.backup` copies for DB inspection and migration tests.
- Open audit DB copies in read-only URI mode and set `PRAGMA query_only=ON` for inspection.
- Do not perform Procore writeback.
- Do not perform Graph, email, calendar, SharePoint, OneDrive, or MCP writeback.
- Do not send or draft emails.
- Do not mutate calendars.
- Do not commit raw payloads, DB copies, private URLs, signed URLs, tokens, secrets, raw HTML, raw email/calendar/document bodies, or raw Procore evidence.
- Do not use cloud LLMs.
- Do not recommend cloud persistence for Procore raw data.
- Do not make raw Procore payloads visible in daily brief, polished browser brief, Obsidian brief, status JSON, test snapshots, or repo evidence.

## Required branch

Create a new implementation branch from clean `main`:

```bash
cd /Users/bobbyfetting/hb-personal-assistant
git fetch origin
git checkout main
git pull --ff-only origin main
git status --short --untracked-files=all
git checkout -b feature/procore-structured-analytics-foundation
```

Stop if the tree is dirty unless the only untracked files are the copied package/evidence materials you are about to manage.

## Required baseline commands

Run and capture results in `docs/evidence/procore_endpoint_structured_analytics_foundation/00-branch-and-baseline/`:

```bash
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git rev-parse main
git rev-parse origin/main
git status --short --untracked-files=all
git branch --contains HEAD
git log --oneline --decorate --graph -50 --all
git branch --all --sort=-committerdate | head -80
git tag --sort=-creatordate | head -30
```

Also verify whether `config/config.yml` exists and whether it is tracked or foreign.

## Required safe production DB copy

Use the app path policy first:

```bash
python - <<'PY'
from hb_assistant.config.path_policy import PathPolicy
print(PathPolicy().get_db_path())
PY
```

Then create a safe audit copy:

```bash
TS="$(date +%Y%m%d-%H%M%S)"
PROD_DB="$HOME/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"
AUDIT_ROOT="/tmp/hb-procore-structured-analytics-foundation-audit-$TS"
AUDIT_DB="$AUDIT_ROOT/prod-backup-$TS.sqlite"

mkdir -p "$AUDIT_ROOT"
pgrep -af "hb-assistant|uvicorn|daily-run|daily-source-refresh|scheduler" > "$AUDIT_ROOT/active-processes-before-backup.txt" || true
ls -lh "$PROD_DB" | tee "$AUDIT_ROOT/prod-db-ls.txt"
shasum -a 256 "$PROD_DB" | tee "$AUDIT_ROOT/prod-db-before.sha256"
sqlite3 "$PROD_DB" ".backup '$AUDIT_DB'"
shasum -a 256 "$AUDIT_DB" | tee "$AUDIT_ROOT/audit-db-backup.sha256"
sqlite3 "$AUDIT_DB" "PRAGMA integrity_check;" | tee "$AUDIT_ROOT/audit-db-integrity-check.txt"
sqlite3 "$AUDIT_DB" "PRAGMA quick_check;" | tee "$AUDIT_ROOT/audit-db-quick-check.txt"
```

Hash mismatch between production and backup is acceptable for a live SQLite source only if the backup opens and integrity/quick checks return `ok`.

## Implementation architecture

Implement a layered local Procore analytics model.

### Layer 0 — Capture/control

Add or extend local-only tables/receipts for:

- endpoint contracts
- capture runs
- endpoint page/request receipts
- project/company scope resolution
- request fingerprints
- endpoint coverage diagnostics
- capture gaps and fail-closed reasons

### Layer 1 — Raw payload landing/snapshots

Add a governed raw landing table, for example:

`procore_endpoint_raw_payloads`

Minimum fields:

- `raw_payload_id`
- `capture_run_id`
- `endpoint_key`
- `endpoint_family`
- `endpoint_version`
- `company_id`
- `company_id_hash`
- `project_id`
- `project_id_hash`
- `project_key`
- `record_type`
- `record_id`
- `record_id_hash`
- `parent_record_id`
- `parent_record_id_hash`
- `source_ref_hash`
- `request_fingerprint_hash`
- `payload_hash`
- `payload_json`
- `payload_size_bytes`
- `payload_captured_at_utc`
- `payload_seen_first_utc`
- `payload_seen_last_utc`
- `is_current`
- `redaction_status`
- `security_scrub_status`
- `contains_personal_data`
- `contains_signed_url`
- `contains_secret_like_value`
- `retention_class`
- `analytics_eligible`
- `raw_procore_payload_persisted`
- `external_writeback_performed`
- `created_utc`
- `updated_utc`

This table exists for replay, auditability, source traceability, and lossless local reprocessing. It is not the analytics surface by itself.

### Layer 2 — Structured endpoint-family bronze tables

Add endpoint-family tables that preserve Procore business content in typed, queryable fields. The implementation must prefer structured endpoint tables over a generic JSON-only sink.

Required minimum family coverage for this package:

1. RFIs and RFI responses.
2. Submittals, responses, and packages.
3. Observations and punch items.
4. Meetings, meeting details, and meeting topics.
5. Daily logs by subtype.
6. Inspections, inspection sections, and inspection items.
7. Schedules and activities.
8. Commitments, purchase orders, prime contracts, and line items.
9. Change events, RFQs, RFQ responses, and change-order families.
10. Budget views, budget rows, budget changes, budget modifications, and amount facts.
11. Subcontractor invoices, invoice items, billing periods, and payment applications where available.
12. Attachments, companies, people, and locations as dimensions/reference tables.

Each structured table must include stable source identity, endpoint identity, company/project identity, parent-child identity where applicable, current/historical state columns, source timestamps, capture timestamps, payload hash and raw payload id, business status columns, owner/BIC/assignee/responsible-party columns where applicable, due/date columns where applicable, cost/schedule/materiality fields where applicable, free-text/business text fields where analytics-relevant and locally allowed, JSON columns only for nested arrays/objects that do not justify child tables yet, security/retention/governance columns, and indexes for endpoint/project/date/status/owner/cost-code/record-id where applicable.

### Layer 3 — Silver projections

Build normalized projections from structured bronze tables: project identity map, person/company/location dimensions, due-date facts, status facts, financial amount facts, WBS/cost-code facts, schedule exposure facts, quality/safety/compliance facts, relationship edges, and current-state indexes.

Existing `procore_financial_*`, `procore_inspection_*`, `procore_record_edges`, `procore_action_signals`, and timeline tables may be reused or reconciled, but the implementation must document which are silver projections versus raw/bronze structured tables.

### Layer 4 — Gold/read models

Build downstream read models: analytics coverage reports, project health/risk marts, ranked Procore signals, daily brief action candidates, candidate source refs, local model context packets, and operator CLI/status surfaces.

Daily brief output must be redacted, capped, source-linked, and usefulness-gated.

## Required one-shot prompt sequence

Execute these in order. Do not skip prompts unless an earlier stop condition applies.

1. `prompts/00_shared_context.md`
2. `prompts/01_repo_truth_db_audit_and_schema_baseline.md`
3. `prompts/02_structured_endpoint_data_contract.md`
4. `prompts/03_capture_runs_and_raw_payload_landing.md`
5. `prompts/04_typed_endpoint_family_tables.md`
6. `prompts/05_backfill_reprocessing_and_coverage.md`
7. `prompts/06_ranked_signals_candidates_and_downstream_consumers.md`
8. `prompts/07_operator_analytics_cli_and_evidence_surfaces.md`
9. `prompts/08_validation_safety_and_final_handoff.md`

## Required evidence structure

Create evidence under:

`docs/evidence/procore_endpoint_structured_analytics_foundation/`

Required structure:

```text
docs/evidence/procore_endpoint_structured_analytics_foundation/
  00-branch-and-baseline/
  01-db-audit-and-schema-baseline/
  02-structured-endpoint-data-contract/
  03-capture-runs-and-raw-payload-landing/
  04-typed-endpoint-family-tables/
  05-backfill-reprocessing-and-coverage/
  06-ranked-signals-candidates-and-downstream-consumers/
  07-operator-analytics-cli-and-evidence-surfaces/
  08-validation-and-final-handoff/
```

Each directory must include `README.md`, `validation-commands.txt`, `validation-results.md`, `changed-files.txt`, `safety-scan-results.txt`, DB-copy proof where applicable, no-raw-leak proof where applicable, and final operator-facing output artifacts where applicable.

Do not include raw Procore payload data or private DB extracts in evidence.

## Required validation

At minimum: fresh DB migration test, copied production DB migration test, rollback/reversibility notes, endpoint contract tests, raw payload landing tests, structured endpoint table insert/update tests, idempotency tests, payload hash/source-ref tests, security scrubbing tests for tokens/signed URLs/secrets, no-writeback tests, no raw leak to daily brief/status/evidence tests, endpoint-family mapper tests, backfill/reprocessing tests with no live Procore calls, structured coverage report tests, ranked signal tests, aggregate-sludge suppression tests, closed-record suppression tests, daily-brief candidate/source-ref tests, local model deterministic fallback tests, CLI JSON/Markdown tests, and production DB unchanged proof during validation.

## Stop conditions

Stop and produce a blocked handoff if production DB cannot be safely backed up, the copied DB fails integrity or quick checks, fresh or copied DB migration tests fail, endpoint identity/idempotency cannot be established, structured table design would collapse into a generic JSON-only dump, payload capture would store tokens/secrets/signed URL query strings/private credentials without security scrubbing, raw payloads appear in daily brief/status/browser/Obsidian/test snapshots/repo evidence, any external writeback path is invoked, reprocessing requires live Procore calls, source refs cannot be preserved from raw/structured record to projection to candidate/read model, aggregate-sludge suppression cannot be proven, tests fail due to package changes, or the implementation requires broad unrelated changes outside Procore ingestion, Procore persistence, analytics/read models, or daily-brief/local-model projection surfaces.

## Expected final handoff

Use `templates/final_handoff_template.md`. Include branch and commit SHA, schema changes, structured endpoint table inventory, raw landing table summary, endpoint coverage before/after, backfill/reprocessing command examples, analytics query examples, daily-brief downstream changes, validation results, safety/no-writeback proof, production DB unchanged proof, known limitations, and next recommended step.
