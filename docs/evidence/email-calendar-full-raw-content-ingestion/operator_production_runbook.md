# Operator Production Runbook — Email + Calendar Full Raw Local DB Storage

**Documented for Bobby to run manually. NOT executed during this work.** Enables full raw
email/calendar content ingestion into the private local SQLite DB and (re)projects it into the
structured layer, while outbound surfaces stay redacted by default.

## Preconditions

- Repo clean; this branch reviewed/merged as intended.
- Production DB backed up (Time Machine ok). Capture its hash first:
  ```bash
  PROD="$(.venv/bin/python3.12 -c 'from hb_assistant.config.path_policy import PathPolicy; print(PathPolicy().get_db_path())')"
  shasum -a 256 "$PROD"
  ```
- Graph scopes already sufficient (read-only mail/calendar); no new tenant/admin consent.
- Raw content policy intentionally enabled (`resources/config/phase_10a_raw_content_policy.seed.yaml`:
  `enabled: true`, `mode: email_calendar`, `starting_sources.email/calendar: true`).

## Config checklist

```text
raw_content.enabled:                      true
raw_content.mode:                         email_calendar
raw_content.starting_sources.email:       true
raw_content.starting_sources.calendar:    true
mail.max_full_body_fetch_per_run:         <bounded>
calendar.max_items_per_run:               <bounded>
outbound_default:                         redacted
model_context.include_raw_content:        true (bounded)
```

## 1. Dry-run ingest (no writes; bounded)

```bash
.venv/bin/hb-assistant graph email index --dry-run --include-raw-content --json
.venv/bin/hb-assistant graph calendar index --dry-run --include-raw-content --json
```
Expect: raw candidate counts; zero DB writes; no stdout raw body; source-quality preview only.

## 2. Apply ingest (bounded; mutates the PRODUCTION DB — intentional)

```bash
.venv/bin/hb-assistant graph email index --apply --include-raw-content --json
.venv/bin/hb-assistant graph calendar index --apply --include-raw-content --json
```
This is the ONLY step that intentionally mutates production. Source-quality is classified on write;
a lower-quality re-capture never downgrades existing full-body rows.

## 3. (Re)project raw → structured (idempotent)

Validate first on a /tmp copy, then apply to production:
```bash
TS="$(date +%Y%m%d-%H%M%S)"; COPY="/tmp/hb-ec-$TS.sqlite"
.venv/bin/python3.12 - <<PY
import sqlite3; s=sqlite3.connect("$PROD"); d=sqlite3.connect("$COPY")
with d: s.backup(d)
PY
.venv/bin/hb-assistant email-calendar raw projection-reprocess --db "$COPY" --apply --no-dry-run --json
.venv/bin/hb-assistant email-calendar raw projection-coverage  --db "$COPY" --json   # expect ok=true, 0 unmapped
# then, intentionally, against production:
.venv/bin/hb-assistant email-calendar raw projection-reprocess --db "$PROD" --apply --no-dry-run --json
```

## 4. Post-apply diagnostics (counts only)

```bash
.venv/bin/hb-assistant email-calendar raw status            --db "$PROD" --json
.venv/bin/hb-assistant email-calendar raw projection-coverage --db "$PROD" --json
```
Expect: raw + structured rows > 0; source_quality distribution includes `graph_full_body` /
`graph_full_event_body` where full body existed; zero unmapped business fields.

## 5. No-leak check over any captured output

```bash
.venv/bin/hb-assistant email-calendar raw no-raw-leak-scan --path <evidence-or-log-dir> --json
```

## Disable / rollback

1. Set `raw_content.enabled: false` (re-run `status` to confirm raw disabled).
2. Keep raw + structured rows (they are local-private); do not purge without a separate approved
   package. Structured tables are additive and harmless when raw mode is off.

## Proving production was only mutated during the intentional apply

`shasum -a 256 "$PROD"` before any audit/validation and again after — it changes ONLY across the
intentional step 2/3 apply, never during dry-run, status, coverage, or /tmp-copy validation.
