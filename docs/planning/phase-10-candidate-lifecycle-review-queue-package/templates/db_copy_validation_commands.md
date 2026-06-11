# DB Copy Validation Commands

```bash
cd /Users/bobbyfetting/hb-personal-assistant

TS="$(date +%Y%m%d-%H%M%S)"
AUDIT_ROOT="/tmp/hb-phase10-candidate-lifecycle-validation-$TS"
mkdir -p "$AUDIT_ROOT"

PROD_DB="/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"
COPY_DB="$AUDIT_ROOT/validation-copy.sqlite"

ps aux | rg "hb-assistant|daily-run|source-refresh|scheduler" || true
lsof "$PROD_DB" || true

shasum -a 256 "$PROD_DB" | tee "$AUDIT_ROOT/prod-db-sha-before.txt"
cp "$PROD_DB" "$COPY_DB"
sqlite3 "$COPY_DB" "PRAGMA integrity_check;" | tee "$AUDIT_ROOT/integrity-before.txt"

# Run lifecycle apply/idempotency checks only against $COPY_DB.
# Example placeholders; adjust to implemented CLI:
hb-assistant second-brain candidates review --db "$COPY_DB" --json > "$AUDIT_ROOT/review-before.json"
hb-assistant second-brain candidates feedback --db "$COPY_DB" --json > "$AUDIT_ROOT/feedback-before.json"

sqlite3 "$COPY_DB" < docs/planning/phase-10-candidate-lifecycle-review-queue-package/templates/raw_safe_sql_checks.sql > "$AUDIT_ROOT/raw-safe-sql-checks.txt"
sqlite3 "$COPY_DB" < docs/planning/phase-10-candidate-lifecycle-review-queue-package/templates/lifecycle_validation_sql.sql > "$AUDIT_ROOT/lifecycle-validation-sql.txt"

sqlite3 "$COPY_DB" "PRAGMA integrity_check;" | tee "$AUDIT_ROOT/integrity-after.txt"
shasum -a 256 "$PROD_DB" | tee "$AUDIT_ROOT/prod-db-sha-after.txt"
diff "$AUDIT_ROOT/prod-db-sha-before.txt" "$AUDIT_ROOT/prod-db-sha-after.txt"
```

