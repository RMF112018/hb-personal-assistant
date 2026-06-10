# No-leak scan

Scanned the changed source, the changed test, and this evidence bundle with the in-repo
`procore analytics no-raw-leak-scan` surface plus a direct pattern grep.

```
$ hb-assistant procore analytics no-raw-leak-scan \
    --path src/hb_assistant/procore/structured_analytics.py \
    --path tests/test_procore_structured_analytics_foundation.py \
    --path docs/evidence/procore_endpoint_structured_analytics_foundation/09-financial-amount-remediation \
    --json
{ "ok": true, "unsafe_finding_count": 0 }

$ grep -rIEn 'token=|Bearer |access_token|X-Amz-Signature|private_url|BEGIN .*PRIVATE KEY' \
    docs/evidence/.../09-financial-amount-remediation
NONE FOUND (clean)
```

The evidence bundle records only field **names**, counts, coverage percentages, and a content
SHA. No raw Procore payload bodies, monetary values, tokens, signed URLs, or PEMs appear. No
`.db`/`.sqlite`/`.env`/`__pycache__`/`.pyc`/dump artifacts were added to the repo (all DB work
used disposable `/tmp` copies).
