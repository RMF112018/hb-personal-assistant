# Validation Commands

Adjust exact test names to repo truth.

## Static / Unit

```bash
cd /Users/bobbyfetting/hb-personal-assistant
source .venv/bin/activate

python -m compileall src tests

pytest -q \
  tests/test_phase_10_daily_run*.py \
  tests/test_phase_10_daily_brief*.py \
  tests/test_phase_10_procore*.py \
  tests/test_phase_10_calendar*.py \
  tests/test_phase_10*_source*.py
```

## Changed-file lint/type

```bash
CHANGED="$(git diff --name-only main...HEAD | grep -E '\.py$' || true)"
if [ -n "$CHANGED" ]; then
  ruff check $CHANGED
  mypy $CHANGED || true
fi
```

## DB Copy Proof

```bash
TS="$(date +%Y%m%d-%H%M%S)"
PROD_DB="$HOME/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"
AUDIT_ROOT="/tmp/daily-brief-usefulness-repair-$TS"
AUDIT_DB="$AUDIT_ROOT/prod-copy.sqlite"
TEST_VAULT="$AUDIT_ROOT/vault"
TEST_HTML="$AUDIT_ROOT/html"
TEST_STATUS="$AUDIT_ROOT/status"

mkdir -p "$AUDIT_ROOT" "$TEST_VAULT" "$TEST_HTML" "$TEST_STATUS"
sqlite3 "$PROD_DB" ".backup '$AUDIT_DB'"
sqlite3 "$AUDIT_DB" "PRAGMA integrity_check;" | tee "$AUDIT_ROOT/integrity_check.txt"
sqlite3 "$AUDIT_DB" "PRAGMA quick_check;" | tee "$AUDIT_ROOT/quick_check.txt"

shasum -a 256 "$PROD_DB" | tee "$AUDIT_ROOT/prod-before.sha256"

.venv/bin/hb-assistant second-brain daily-run run \
  --apply \
  --raw \
  --write-obsidian \
  --confirm-vault-write \
  --vault-brief-dir "$TEST_VAULT" \
  --browser-output-dir "$TEST_HTML" \
  --status-dir "$TEST_STATUS" \
  --db "$AUDIT_DB" \
  --json | tee "$AUDIT_ROOT/daily-run-copy-apply.json"

shasum -a 256 "$PROD_DB" | tee "$AUDIT_ROOT/prod-after.sha256"

python -m json.tool "$AUDIT_ROOT/daily-run-copy-apply.json" > "$AUDIT_ROOT/daily-run-copy-apply.pretty.json"
cat "$TEST_STATUS/latest-status.json" | python -m json.tool > "$AUDIT_ROOT/latest-status.pretty.json"
```

## Forbidden Scan

Scan changed repo evidence plus `/tmp` status/output summaries. Do not scan raw DB.

```bash
python - <<'PY'
from pathlib import Path
import re, sys

roots = [Path("docs/evidence/daily-brief-usefulness-repair")]
patterns = [
    r"Bearer\s+",
    r"access_token",
    r"refresh_token",
    r"client_secret",
    r"sig=",
    r"signed_url",
    r"join_url",
    r"raw_prompt",
    r"raw_response",
    r"body_html",
    r"body_text",
]
bad = []
for root in roots:
    if not root.exists():
        continue
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for pat in patterns:
            if re.search(pat, text, re.I):
                bad.append((str(p), pat))
if bad:
    for item in bad:
        print(item)
    sys.exit(1)
print("forbidden scan clean")
PY
```
