# Local Path Repair Runbook

## Purpose

Resolve local Application Support and DB path readiness issues without hiding code defects.

## Inspect

```bash
APP_SUPPORT="$HOME/Library/Application Support/HB Personal Assistant"

ls -lde "$HOME/Library" "$HOME/Library/Application Support" "$APP_SUPPORT" || true
stat -f "%Su %Sg %Sp %N" "$APP_SUPPORT" || true
ls -lae "$APP_SUPPORT" || true
find "$APP_SUPPORT" -maxdepth 3 -print -exec stat -f "%Su %Sg %Sp %N" {} \; 2>/dev/null || true
```

## Repair Candidate

Only run if inspection confirms ownership/permission issue.

```bash
APP_SUPPORT="$HOME/Library/Application Support/HB Personal Assistant"

sudo chown -R "$USER":staff "$APP_SUPPORT"
chmod 700 "$APP_SUPPORT"
mkdir -p "$APP_SUPPORT/auth" "$APP_SUPPORT/evidence" "$APP_SUPPORT/logs" "$APP_SUPPORT/db" "$APP_SUPPORT/cache"
chmod 700 "$APP_SUPPORT/auth" "$APP_SUPPORT/evidence" "$APP_SUPPORT/logs"
chmod 755 "$APP_SUPPORT/db" "$APP_SUPPORT/cache" "$APP_SUPPORT/logs/run-logs" "$APP_SUPPORT/logs/error-logs" 2>/dev/null || true
```

## Validate

```bash
source .venv/bin/activate
hb-assistant diagnostics paths --json
hb-assistant auth status --json
hb-assistant files ingest --dry-run --json
hb-assistant run morning --dry-run --json
```

## Notes

The app should not require repeated manual repairs. If these commands only pass after manual repair but fail again later, fix PathPolicy or the configured path.
