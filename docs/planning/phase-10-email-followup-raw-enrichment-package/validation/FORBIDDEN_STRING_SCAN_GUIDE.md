# Forbidden String Scan Guide

## Objective

Prove committed evidence, generated safe outputs, and selected JSON artifacts contain no unsafe raw content.

## Suggested Scan Targets

```bash
TARGETS=(
  "docs/evidence/phase-10-email-followup-raw-enrichment"
  "/tmp/email_raw_enrichment_dry_run.json"
  "/tmp/email_raw_enrichment_apply.json"
  "/tmp/email_raw_enrichment_apply_again.json"
)
```

Only include `/tmp` files if they are safe/redacted. Do not commit raw `/tmp` files.

## Generic Pattern Scan

```bash
python - <<'PY'
from pathlib import Path
import re

paths = [
    Path('docs/evidence/phase-10-email-followup-raw-enrichment'),
]
patterns = [
    r'https?://',
    r'Bearer\s+',
    r'Authorization:',
    r'access_token',
    r'refresh_token',
    r'id_token',
    r'client_secret',
    r'BEGIN PRIVATE KEY',
    r'teams\.microsoft\.com/l/meetup-join',
    r'join\.microsoft\.com',
    r'zoom\.us/j/',
    r'body_html',
    r'raw_prompt',
    r'raw_response',
]
compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
failures = []
for base in paths:
    if not base.exists():
        continue
    files = [base] if base.is_file() else [p for p in base.rglob('*') if p.is_file()]
    for f in files:
        text = f.read_text(errors='ignore')
        for pat, rx in zip(patterns, compiled):
            if rx.search(text):
                failures.append((str(f), pat))
if failures:
    print('FORBIDDEN STRING SCAN FAILED')
    for f, pat in failures:
        print(f'{f}: {pat}')
    raise SystemExit(1)
print('FORBIDDEN STRING SCAN PASSED')
PY
```

## Local Sensitive Pattern Scan

If Bobby provides local known-sensitive patterns, keep them outside the repo. Example:

```bash
SENSITIVE_PATTERNS=/tmp/hb_sensitive_patterns.txt
python scripts_or_inline_scan.py "$SENSITIVE_PATTERNS"
```

Do not commit the sensitive pattern file.

## Required Evidence

Commit only a redacted summary:

```text
FORBIDDEN STRING SCAN PASSED
Targets: <list>
Pattern families: URL, bearer/auth tokens, OAuth token names, private key marker, meeting join URLs, raw prompt/response markers, body_html marker
Exceptions: none
```
