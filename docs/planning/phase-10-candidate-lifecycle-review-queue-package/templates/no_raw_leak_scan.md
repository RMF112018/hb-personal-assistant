# No Raw Leak Scan Template

Run scans over generated evidence and rendered outputs.

```bash
EVIDENCE_DIR="docs/evidence/phase-10-candidate-lifecycle-review-queue"

rg -n -i \
  "body_html|body_text|raw_body|raw_html|recipients_json|attendees_json|join_url|signed_url|download_url|webLink|Authorization|Bearer|token|secret|prompt|response|<html|</html|https?://" \
  "$EVIDENCE_DIR" \
  > "$EVIDENCE_DIR/09-no-raw-leak-rg.txt" || true
```

Then run the implemented structured no-raw-leak test suite:

```bash
pytest tests/test_phase_10_candidate_lifecycle_no_raw_leak.py
```

Record:

- scanned path
- forbidden patterns
- matches count
- disposition for any match
- final pass/fail

