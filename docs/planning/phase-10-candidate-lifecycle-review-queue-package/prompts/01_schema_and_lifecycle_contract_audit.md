# Prompt 01 — Schema and Lifecycle Contract Audit

## Objective

Decide whether existing schema can represent the unified lifecycle cleanly or whether a minimal additive migration is required.

## DB copy setup

Use `/tmp` only.

```bash
TS="$(date +%Y%m%d-%H%M%S)"
AUDIT_ROOT="/tmp/hb-phase10-candidate-lifecycle-$TS"
mkdir -p "$AUDIT_ROOT"

PROD_DB="/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"
COPY_DB="$AUDIT_ROOT/audit-copy.sqlite"

ps aux | rg "hb-assistant|daily-run|source-refresh|scheduler" || true
lsof "$PROD_DB" || true
shasum -a 256 "$PROD_DB" | tee "$AUDIT_ROOT/prod-db-sha-before.txt"
cp "$PROD_DB" "$COPY_DB"
sqlite3 "$COPY_DB" "PRAGMA integrity_check;"
```

## Required SQL

Run the templates in `templates/raw_safe_sql_checks.sql` and inspect:

- candidate/domain tables
- accepted-action tables
- follow-up watch tables
- review event tables
- candidate source-ref coverage
- project-key coverage
- guard-column sums
- existing lifecycle/disposition/merge/suppression/feedback tables if present

## Design decision

Prefer no migration if possible.

A migration is justified if existing tables cannot cleanly represent:

- lifecycle events for `daily_brief_action_candidates`
- merge links between candidates and accepted items
- recurring duplicate suppression by group key
- closed/reopened state across accepted/watch/daily-brief families
- feedback summary derived from accepted/rejected/snoozed/suppressed/merged patterns

If migration is required, implement only additive VNext tables:

- `candidate_lifecycle_events`
- `candidate_merge_links`
- `candidate_suppression_rules`

Do not add a materialized `candidate_review_queue` unless the audit proves a persisted queue is necessary.

## Evidence

Write:

- `01_schema_audit.json`
- a short migration decision section in `00_repo_truth.md`

Allowed output: table names, columns, row counts, coverage percentages, hashes/counts, reason codes. No raw content.

