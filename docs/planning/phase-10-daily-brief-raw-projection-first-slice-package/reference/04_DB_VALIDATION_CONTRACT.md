# Reference — DB Validation Contract

## Copy first

```bash
DB_SRC="$HOME/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
ROLL="/tmp/hb-first-slice-$TS"
mkdir -p "$ROLL"
python - <<'PY'
from pathlib import Path
import hashlib, shutil, os, json
src = Path.home()/"Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"
roll = Path(os.environ.get("ROLL", "/tmp/hb-first-slice-manual"))
roll.mkdir(parents=True, exist_ok=True)
dst = roll/"audit-copy.sqlite"
shutil.copy2(src, dst)
def h(p):
    x=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024), b''):
            x.update(b)
    st=p.stat()
    print(json.dumps({"path": str(p), "sha256": x.hexdigest(), "size": st.st_size, "mtime_ns": st.st_mtime_ns}, indent=2))
h(src); h(dst)
PY
```

## Query mode

Use read-only URI where possible and set:

```sql
PRAGMA query_only=ON;
PRAGMA quick_check;
```

## Output policy

Safe:

- table names
- column names
- row counts
- null/non-null counts
- grouped counts by enum/source family/source quality/status/reason code
- hashes
- guard-column sums

Unsafe:

- raw subjects/titles/bodies
- raw HTML
- raw prompt/response text
- URLs
- tokens/secrets
- attendee/recipient arrays
- source payload values
