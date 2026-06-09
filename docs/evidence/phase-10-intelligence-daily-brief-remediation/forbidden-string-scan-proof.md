# Forbidden-String Scan Proof

The `VALIDATION_COMMANDS.md` forbidden-string scanner was run over the committed evidence directory
`docs/evidence/phase-10-intelligence-daily-brief-remediation/` (all `.md` and `.json` files).

| Category | Pattern | Result |
| --- | --- | --- |
| url | `https?://` | none |
| email | RFC-ish address | none |
| join-link | meeting word + url | none |
| token | access / refresh token, client secret, API key, bearer-prefixed value | none |
| pem | PEM private-key header | none |

Result: **forbidden scan clean** (exit 0).

Additional checks:
- Each scrubbed JSON summary contains **no** `intelligence` object and **no** raw bullet `text` field
  (only counts, profile ids, model names, status/reason codes, latency, coverage, pass/fail).
- `git diff --check` reports no whitespace errors on the staged evidence (see final audit).

Raw `/tmp` captures (which include model bullet text) were intentionally **not** committed.
