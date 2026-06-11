# No-Raw-Leak Scan

## Command

Use the current repo command. Expected:

```bash
EVIDENCE_DIR="docs/evidence/phase-10-email-followup-candidate-projection"

.venv/bin/hb-assistant email-calendar raw no-raw-leak-scan \
  --path "$EVIDENCE_DIR" \
  --json \
  2>&1 | tee "$EVIDENCE_DIR/09-no-raw-leak-scan.json"
```

If the command shape differs, inspect:

```bash
.venv/bin/hb-assistant email-calendar raw --help
rg -n "no-raw-leak|no_raw_leak_scan|raw leak|egress" src tests
```

## Sentinel Assertions

Add tests with synthetic sentinels for:

- body text
- HTML
- join URL
- signed URL
- token
- secret
- recipient array
- model prompt
- model response

Assert sentinels are absent from:

- extractor output
- persistence rows
- source refs
- status JSON
- rendered brief
- evidence files

## Required Evidence Statement

```text
No raw body text, raw HTML, full recipient arrays, private URLs, join URLs, signed URLs, tokens, secrets, model prompts, or model responses were found in evidence/status/output surfaces. Raw access count: <n>. All raw access events were audited: yes/no.
```
