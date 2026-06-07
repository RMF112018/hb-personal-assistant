# Raw Content Dev Validation Runbook

```bash
export HB_PA_CONFIG=/tmp/hb-pa-dev-live.yml
DB="$HOME/Library/Application Support/HB Personal Assistant (Dev)/db/hb-personal-assistant.sqlite"

hb-assistant graph raw-content status --json
hb-assistant graph mail discover --lookback-days 30 --max-messages 200 --no-dry-run --include-raw-content --json
hb-assistant graph mail thread-summary --lookback-days 30 --max-threads 200 --no-dry-run --include-raw-content --json
hb-assistant construction-agent refresh-sources --graph-only --apply --confirm --skip-vector --skip-daily-brief-proof --include-raw-content --json
```

Validate:

```bash
sqlite3 "$DB" "
SELECT 'email_message_raw_content', COUNT(*) FROM email_message_raw_content
UNION ALL SELECT 'email_thread_raw_context', COUNT(*) FROM email_thread_raw_context
UNION ALL SELECT 'calendar_event_raw_content', COUNT(*) FROM calendar_event_raw_content;
"
```
