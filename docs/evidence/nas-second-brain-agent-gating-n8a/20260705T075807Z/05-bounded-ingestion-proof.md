# 05 — Bounded Ingestion Proof (Reference to N8 PASS)

**N8A performs no new ingestion.** The bounded single-scope ingestion already ran live and **PASS** in N8, including the first live-DB write and the V99 migration.

## Reference

- **N8 live proof:** `../../nas-second-brain-agent-gating-n8/live-20260704/05-live-bounded-ingestion-proof.md` — **PASS**.
  - Mandatory backup first → `.../db/backups/proof05-20260704T211230Z` (main-DB SHA `2359ec12…`, size-verified == live DB).
  - Schema migrate **v98 → v99**; **V99 remap of 9,128 existing file `source_id`s** across 8 FK'd tables (deferred FKs, zero row loss).
  - Bounded scan over `source_root_key=nas_test`: `scanned 3 / indexed 3 / skipped 0 / deleted 0 / errors 0 / truncated false`. Row deltas `sources/metadata/text/chunks` each **+3**; relationships/generated_notes/summaries/events unchanged.
  - DB: `/volume2/personal-assistant/app-support/db/hb-personal-assistant.sqlite`. Card/summary/watcher generation disabled in the ingest config (one-shot ingest only).

## N8A confirmation (read-only, this session)

**Confirmed at rest (non-sudo):** the proof05/06/07 backup rollback points are present under `…/db/backups/`, and the ingestion's downstream card is present (`06`). The DB is `0600` svc-owned, so the definitive V99 + `nas_test` row-count read is a **pending optional root read-only pass** (`../live-20260705T075807Z/00-live-index.md` item 2) — not a blocker; N8 live proof 05 already recorded V99 + 3 `nas_test` rows at write time and no re-ingestion occurred.

## Verdict

**PASS by reference** (N8 live 05, incl. V99); backups + downstream card confirmed at rest. No new write.
