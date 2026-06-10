# 10 — Final handoff

- **Branch:** `fix/procore-full-raw-payload-ingestion`
- **Commit SHA:** `c608a916204e13dafba2581fece7ab092241cbe2`
- **Schema version decision:** **V46 retained** (no V47 — existing columns express
  source-quality / persistence / no-writeback; precedence enforced in application code).
- **Status:** READY FOR REVIEW

## Changed files

- `src/hb_assistant/procore/structured_analytics.py` — full-raw persistence API,
  transport-only scrubber, placeholder cleaner, source-quality precedence, structured
  projection from full payloads, `backfill_from_raw_payloads`, legacy no-downgrade guard,
  diagnostics.
- `src/hb_assistant/procore/live_sync.py` — raw-first persistence in the main + inline
  N+1 child loops; `raw_persist_error_count` verdict downgrade; receipt fields.
- `src/hb_assistant/cli/procore.py` — `analytics reprocess` full-then-legacy source order
  + `--source auto|full|legacy`; preserved top-level keys.
- `tests/test_procore_full_raw_payload_ingestion.py` — new acceptance suite (11 tests).
- `docs/architecture/200-procore-full-raw-payload-ingestion.md` — design record.
- `docs/evidence/procore_full_raw_payload_ingestion/**` — this evidence bundle.

## Proofs

1. **Full raw persisted to DB:** `payload_json` stores the full endpoint item (transport
   secrets stripped) with `raw_procore_payload_persisted=1`,
   `source_quality∈{live_full_payload,fixture_full_payload}` — see `03` / `04`.
2. **Redacted legacy is fallback only:** `backfill_from_live_records` keeps
   `source_quality='redacted_legacy_projection'` / `persisted=0` and is skipped where a
   full row exists — see `02` / `06`.
3. **Structured projects from full values:** amount/owner/cost_code/dates populate from
   the full payload where the redacted projection leaves them NULL — see `05`.
4. **Legacy cannot downgrade full rows:** rank guard at structured `record_key` + raw
   identity; `skipped_due_to_higher_quality` reported — see `06`.
5. **No leak:** receipts/stdout/evidence carry no payload bodies; scan matches are
   detector literals / pre-existing auth code — see `04` / `07`.
6. **Production untouched:** sha256 identical before/after; all writes on `/tmp` copies
   + fixtures — see `08`.

## Validation

11 new + 18 foundation + 45 live-sync chain tests pass; broad procore sweep green (1
skip); ruff + mypy clean. One pre-existing, unrelated launcher env-leak failure (same on
clean `main`).

## Post-merge production apply

See `09-operator-production-runbook.md` for the exact gated `procore live sync` +
`analytics reprocess` + verification commands (with backup and sha capture).

## Known limitations

- Legacy `procore_live_records` projection and the `project_*` enrichment paths are
  retained unchanged (full-raw persistence runs alongside, raw-first).
- Existing production rows stay `redacted_legacy_projection` until each endpoint family
  is re-synced live; `reprocess` upgrades any record that has a full raw row.
- `payment-applications` remains source-absent (no live rows emitted today); mapped so
  amounts populate automatically if/when rows arrive.
