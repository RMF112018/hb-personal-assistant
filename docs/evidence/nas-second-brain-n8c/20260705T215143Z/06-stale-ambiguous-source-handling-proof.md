# 06 — Stale / Ambiguous / Deleted Source Handling Proof

The card-aware orchestrator `extract_claims_for_card` (`claim_extraction.py`) integrates N8C-2 identity
+ N8C-3 navigation before writing any claim. Source: `tests/test_claim_extraction.py`.

## Gating logic
1. **Ambiguous card→source link** → **block**. `identity.get_source_for_card(note_rel_path)` resolution
   `ambiguous` raises `ClaimExtractionBlocked`; no claim written
   (`test_ambiguous_link_blocks`, asserts `count_claims()==0`).
2. **Deleted source** → **block**. `identity.classify_card_state` state `source_deleted` raises
   (`test_deleted_source_blocks`, `count==0`).
3. **Stale source** → **block by default, labeled if opted in**. Stale/missing state raises unless
   `allow_stale_source=True`; then claims are written with `source_state="stale"`
   (`test_stale_source_blocks_then_labels`).
4. **Current source** → extract, label `source_state="current"`, link to `source_id` + card
   `note_rel_path` + `card_id` (`test_extract_for_card_links_and_labels`).

## Content path
Extraction input is the **source's** bounded, redaction-safe indexed text via the approved N8C-3
`source_navigation.get_source` (the graph-safe summary card embeds no raw text). Content is never read
by raw filesystem access here; the vault-note path retains its N8C-3 path-safety.

## No auto-run
`test_no_claims_until_explicit_call` — the fixture indexes sources and generates cards but runs NO
extraction; `count_claims()==0`. Importing `claim_extraction` / `claim_repository` performs no
extraction or writes (verified). Claims exist only after an explicit orchestrator/seam/test call.

## Freshness fields
`assistant_claims` carries `status` (incl. `stale`, `superseded`), `source_state`, `valid_until`,
`stale_after`, `superseded_by`, and `mark_stale()` — the hooks a future maintenance loop needs. N8C-4
adds no scheduled stale scan.
