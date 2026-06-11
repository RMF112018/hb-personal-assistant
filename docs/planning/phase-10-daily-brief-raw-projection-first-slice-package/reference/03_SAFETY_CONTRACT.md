# Reference — Safety Contract

## Hard rules

- All validation apply commands use `/tmp` DB copies only.
- Production DB must be proven unchanged by hash, size, and mtime.
- Evidence contains counts, hashes, statuses, table names, column names, source-family labels, reason codes, and timestamps only.
- Never print, commit, or persist raw values from private tables.
- Candidate source refs should use hashes or deterministic review-safe refs only.
- No external writeback.
- No cloud LLM routes.

## Raw access

Allowed raw access is local-only, bounded, and audited. Raw body reads must go through existing `load_body(...)` / body-ref style paths where available and must write `raw_content_access_events`.

## Structured projection

Structured tables must not duplicate raw body fields or join URLs. Use body availability flags, char counts, raw row ids, source quality, payload hash, and sidecar policy fields.

## Evidence scans

Run no-raw-leak scans over the evidence directory and any generated status/browser/markdown proof files. Add extra sentinels only if they are synthetic and safe.
