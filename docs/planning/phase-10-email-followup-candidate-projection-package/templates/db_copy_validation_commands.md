# DB Copy Validation Commands

```bash
cd /Users/bobbyfetting/hb-personal-assistant

TS="$(date +%Y%m%d-%H%M%S)"
AUDIT_ROOT="/tmp/hb-phase10-email-followup-candidate-projection-$TS"
mkdir -p "$AUDIT_ROOT"

PROD_DB="/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"
COPY_DB="$AUDIT_ROOT/audit-copy.sqlite"

cp "$PROD_DB" "$COPY_DB"

sqlite3 "$COPY_DB" "PRAGMA integrity_check;"
sqlite3 "$COPY_DB" "PRAGMA quick_check;"
sqlite3 "$COPY_DB" "PRAGMA user_version;"
sqlite3 "$COPY_DB" < docs/planning/phase-10-email-followup-candidate-projection-package/templates/raw_safe_sql_checks.sql \
  | tee "$AUDIT_ROOT/raw-safe-sql-checks.txt"
```

Apply validation only on copy:

```bash
.venv/bin/hb-assistant second-brain local-ai daily-run \
  --db "$COPY_DB" \
  --apply \
  --json \
  2>&1 | tee "$AUDIT_ROOT/daily-run-apply-1.json"

.venv/bin/hb-assistant second-brain local-ai daily-run \
  --db "$COPY_DB" \
  --apply \
  --json \
  2>&1 | tee "$AUDIT_ROOT/daily-run-apply-2.json"
```

If the CLI path differs, inspect current Typer commands and use the repo-truth equivalent. Keep `--db "$COPY_DB"` explicit.
