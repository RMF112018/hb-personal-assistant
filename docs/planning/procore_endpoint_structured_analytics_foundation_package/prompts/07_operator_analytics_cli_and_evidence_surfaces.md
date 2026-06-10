# 07 — Operator Analytics CLI and Evidence Surfaces

## Objective

Expose safe operator-facing CLI/status/report surfaces for the new Procore structured analytics foundation.

## Required surfaces

Add or update CLI commands for endpoint contract inventory, raw landing coverage, structured table coverage, endpoint-family analytics readiness, backfill/reprocessing preview, source-ref coverage, project/family row counts, ranking diagnostics, aggregate-sludge diagnostics, and no-raw-leak validation.

Suggested command shapes, adjusted to repo conventions:

```bash
hb-assistant procore analytics contract --json
hb-assistant procore analytics coverage --json
hb-assistant procore analytics coverage --markdown
hb-assistant procore analytics reprocess --dry-run --family rfis
hb-assistant procore analytics structured-counts --project-key <key> --json
hb-assistant procore analytics ranking-diagnostics --brief-date YYYY-MM-DD --json
hb-assistant procore analytics no-raw-leak-scan --json
```

## Required output behavior

JSON outputs are stable and testable. Markdown outputs are operator-readable. No raw payloads, tokens, signed URLs, private URLs, raw HTML, or secrets appear in outputs. Coverage reports can include counts, hashes, endpoint ids, project keys, row ids, and redacted titles only when safe.

## Evidence

Write evidence under `docs/evidence/procore_endpoint_structured_analytics_foundation/07-operator-analytics-cli-and-evidence-surfaces/`.

Include representative CLI outputs with private data redacted and raw payloads excluded.
