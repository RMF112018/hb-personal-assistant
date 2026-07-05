# 07 — Duplicate-Prevention Proof (Reference to N8 PASS)

**N8A performs no new duplicate-prevention writes.** All four assertions already ran live and **PASS** in N8.

## Reference

- **N8 live proof:** `../../nas-second-brain-agent-gating-n8/live-20260704/07-live-duplicate-prevention-proof.md` — **PASS (all four)**.
  1. **Second-watcher refusal** — real host-stamped lease (`source_intelligence_state`), owner B refused (`acquired=False`) without starting the Observer.
  2. **Duplicate card** — `generate_source_card(overwrite=False)` → `note_already_exists`; `generated_notes` 1→1 via `UNIQUE(source_id, note_rel_path)`.
  3. **SHA overwrite** — `patch_note` with wrong `expected_sha256` → `sha256_mismatch`; card byte-identical.
  4. **Cross-root non-collision** — same `rel_path` under `nas_test` vs `nas_test2` → distinct ids (`482f41ec…` vs `c90eced77a54…`), both rows coexist (V99 root-scoped unique index).

## N8A confirmation (read-only, this session)

**Confirmed at rest:** exactly one `note-a.txt__*.md` card exists under the vault (single hit — no duplicate card), and no new ingestion/card was performed by N8A. The definitive per-table `SELECT COUNT(*)` delta-vs-N8 (proving no duplicate rows) is a pending optional root read-only pass (DB is `0600` svc-owned; `../live-20260705T075807Z/00-live-index.md` item 2). Since N8A wrote nothing, no duplicates could have accumulated since N8's proof 07.

## Verdict

**PASS by reference** (N8 live 07, four assertions); single-card at-rest confirmed, no N8A writes. No duplicates.
