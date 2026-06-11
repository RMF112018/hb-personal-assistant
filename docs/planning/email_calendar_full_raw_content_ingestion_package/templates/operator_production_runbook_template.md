# Operator Production Runbook — Email + Calendar Full Raw Local DB Storage

## Purpose

Enable and validate full raw email/calendar content ingestion into Bobby's private local SQLite DB while keeping outbound surfaces redacted by default.

## Preconditions

- Repo clean.
- Current branch reviewed and merged/pushed as intended.
- Production DB backed up or Time Machine available.
- Graph scopes already sufficient; no new tenant/admin consent required.
- Raw content policy intentionally enabled.

## Config checklist

```text
raw_content.enabled:
raw_content.mode:
raw_content.starting_sources.email:
raw_content.starting_sources.calendar:
mail.max_body_retrieval_per_run:
calendar.max_items_per_run:
outbound_default:
model_context_raw_default:
```

## Dry-run commands

```bash
# Replace with final repo-truth commands
.venv/bin/hb-assistant graph email index --dry-run --include-raw-content --json
.venv/bin/hb-assistant graph calendar index --dry-run --include-raw-content --json
```

Expected dry-run evidence:

- raw candidate counts;
- no production DB raw writes;
- no stdout raw body text;
- source-quality preview only.

## Apply commands

```bash
# Replace with final repo-truth commands after tests pass
.venv/bin/hb-assistant graph email index --apply --include-raw-content --json
.venv/bin/hb-assistant graph calendar index --apply --include-raw-content --json
```

## Post-apply validation

```bash
python docs/planning/email_calendar_full_raw_content_ingestion_package/scripts/email_calendar_raw_probe.py \
  --repo /Users/bobbyfetting/hb-personal-assistant \
  --output /tmp/email-calendar-raw-probe-production-after-apply.json
```

Expected evidence:

- email/calendar raw table row counts > 0 where source has data;
- body_text/body_html null rates explainable;
- source_quality distribution includes `graph_full_body` / `graph_full_event_body` where full body existed;
- no raw body in stdout/logs/evidence;
- raw access events recorded for raw consumer access.

## Disable / rollback

1. Disable raw content policy.
2. Re-run status command to confirm raw disabled.
3. Keep raw rows unless Bobby explicitly wants a purge migration/runbook.
4. Do not destructively purge without a separate approved package.

## Troubleshooting

| Symptom | Likely cause | Safe action |
|---|---|---|
| raw rows = 0 | policy disabled, dry-run only, insufficient Graph fetch, no source data | check policy/status and dry-run counts |
| preview only | Graph body unavailable or body fetch failed | inspect source-quality distribution and redacted errors |
| no access events | raw read wrapper not used | rerun raw consumer tests |
| no meeting prep improvement | consumer still reading metadata path | inspect meeting-prep read model source selection |
