# Procore Full Raw Payload Ingestion — Evidence Bundle

Scrubbed evidence for the change from redacted Procore replay to fully populated
Procore raw/structured analytics storage.

- Branch: `fix/procore-full-raw-payload-ingestion`
- Schema: **V46 retained** (no V47 needed)
- Commit: `c608a916` — `fix(procore): populate raw tables from full endpoint payloads`
- Production DB touched during validation: **No** (read-only sha256 verified unchanged;
  all writes on `/tmp` copies and fixtures)

## Outcome

`procore_endpoint_raw_payloads.payload_json` and the matching `procore_raw_*` structured
rows are now populated from **full live Procore endpoint response payload values**
(transport/auth secrets stripped) instead of `procore_live_records.canonical_json_redacted`.
The redacted legacy projection remains only as an honestly-labelled, lower-precedence
fallback that cannot overwrite or downgrade full data.

## Files

| File | Content |
|---|---|
| `01-repo-truth.md` | Base commit, schema head, redacted-replay boundary, live-sync boundary |
| `02-schema-source-quality.md` | V46-vs-V47 decision, source-quality precedence |
| `03-full-raw-fixture-proof.md` | Full fixture persistence (counts/fields/hashes) |
| `04-live-sync-boundary.md` | Raw-first wiring, receipt fields, no-body proof |
| `05-structured-null-rate-matrix.md` | Full vs redacted field population matrix |
| `06-idempotency-and-precedence.md` | Upgrade / no-downgrade / idempotency sequence |
| `07-no-leak-scan.md` | Secret/signed-URL scan + detector-literal classification |
| `08-validation-results.md` | pytest / ruff / mypy / DB-copy results |
| `09-operator-production-runbook.md` | Exact post-merge production apply commands |
| `10-final-handoff.md` | Branch, SHA, changed files, proofs, limitations |

Evidence contains counts, hashes, field names, percentages and classifications only —
no raw payload bodies, DB files, private text values, secrets, signed URLs, or
token-like values.
