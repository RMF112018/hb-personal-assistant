# 05 — Bounded Manual Ingestion Proof — RUNBOOK (PENDING LIVE EXECUTION WITH BOBBY)

Status: **HOLD** — live NAS, per-step approval required. Not executed this session.

## Plan (exactly one bounded ingestion — one-shot, NOT a continuous watcher)
1. Backend up on the NAS with `HB_NAS_RUNTIME=1` + `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1`
   (workers default-off; ingestion is manual one-shot).
2. Capture **before** row counts (svc, read-only): `SELECT COUNT(*) FROM source_intelligence_sources`
   (+ metadata / generated_notes) on `/volume1/personal-assistant/app-support/db/hb-personal-assistant.sqlite`.
3. Run a single bounded rebuild/drain over the `nas_test` root (one-shot `request_rebuild` drain to empty,
   or a scoped `--include-file`/manifest ingestion of the 2–3 files).
4. Capture **after** row counts + the indexer report (scanned/indexed/skipped/errors).

## Acceptance / receipts
- Row-count delta = number of test files ingested (e.g. +2/+3 `sources`), no unexpected table growth.
- New `source_id`s are root-scoped (`sha256(external_file|file|nas_test|<rel_path>)`).
- Read/mutation receipts captured; **no** continuous watcher started; **no** live-DB write outside this
  one bounded ingestion. No secrets in output.
