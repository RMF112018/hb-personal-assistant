# DB-Copy Proof Commands

## Objective

Prove the implementation on a DB copy without mutating production DB.

## Setup

```bash
cd /Users/bobbyfetting/hb-personal-assistant
SOURCE_DB="<redacted-production-or-dev-db-path>"
PROOF_DB="/tmp/hb_email_followup_raw_enrichment_proof.sqlite"
rm -f "$PROOF_DB"
cp "$SOURCE_DB" "$PROOF_DB"
```

## Baseline

```bash
python - <<'PY'
import os, sqlite3, json
from pathlib import Path
p = Path('/tmp/hb_email_followup_raw_enrichment_proof.sqlite')
con = sqlite3.connect(p)
cur = con.cursor()
tables = ['email_followup_enrichments', 'local_model_run_receipts', 'follow_up_watch_items']
result = {'db': str(p), 'size': p.stat().st_size, 'counts': {}}
for t in tables:
    try:
        result['counts'][t] = cur.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
    except sqlite3.Error as exc:
        result['counts'][t] = f'unavailable: {exc}'
print(json.dumps(result, indent=2))
PY
```

## Dry Run

```bash
.venv/bin/hb-assistant second-brain follow-up-watch scan   --with-raw-enrichment   --db "$PROOF_DB"   --dry-run   --json > /tmp/email_raw_enrichment_dry_run.json
```

Then rerun baseline counts and prove unchanged.

## Apply With Cap

```bash
.venv/bin/hb-assistant second-brain follow-up-watch scan   --with-raw-enrichment   --db "$PROOF_DB"   --apply   --max-persist 10   --json > /tmp/email_raw_enrichment_apply.json
```

## Idempotency

```bash
.venv/bin/hb-assistant second-brain follow-up-watch scan   --with-raw-enrichment   --db "$PROOF_DB"   --apply   --max-persist 10   --json > /tmp/email_raw_enrichment_apply_again.json
```

Prove the second apply does not duplicate rows.

## Production DB Unchanged

Record production DB mtime/size/checksum before and after if safe:

```bash
stat "$SOURCE_DB"
shasum -a 256 "$SOURCE_DB" || true
```

If hashing production DB is too expensive, record mtime/size and explain.
