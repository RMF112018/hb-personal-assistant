# DB Copy Validation Commands

Use this pattern only after implementation. Never apply against production DB.

```bash
cd /Users/bobbyfetting/hb-personal-assistant

PROD="$HOME/Library/Application Support/hb-personal-assistant/construction.db"
if [ ! -f "$PROD" ]; then
  PROD="$HOME/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"
fi

TS="$(date +%Y%m%d-%H%M%S)"
ROLL="/tmp/hb-phase10-effectiveness-$TS"
mkdir -p "$ROLL"

shasum -a 256 "$PROD" | tee "$ROLL/prod-before.sha256"
cp "$PROD" "$ROLL/construction.db"

.venv/bin/hb-assistant second-brain daily-brief evaluate-effectiveness   --db "$ROLL/construction.db"   --brief-date "$(date +%F)"   --dry-run   --json   | tee "$ROLL/effectiveness-dry-run-single-day.json"

.venv/bin/hb-assistant second-brain daily-brief evaluate-effectiveness   --db "$ROLL/construction.db"   --window-start "$(date -v-7d +%F 2>/dev/null || date -d '7 days ago' +%F)"   --window-end "$(date +%F)"   --dry-run   --json   | tee "$ROLL/effectiveness-dry-run-window.json"

.venv/bin/hb-assistant second-brain daily-brief evaluate-effectiveness   --db "$ROLL/construction.db"   --window-start "$(date -v-7d +%F 2>/dev/null || date -d '7 days ago' +%F)"   --window-end "$(date +%F)"   --apply   --max-persist 500   --json   | tee "$ROLL/effectiveness-apply.json"

sqlite3 "$ROLL/construction.db" < docs/planning/phase-10-daily-brief-effectiveness-ranking-policy-telemetry-package/templates/raw_safe_sql_checks.sql   | tee "$ROLL/raw-safe-sql-checks.txt"

shasum -a 256 "$PROD" | tee "$ROLL/prod-after.sha256"
diff "$ROLL/prod-before.sha256" "$ROLL/prod-after.sha256"
```
