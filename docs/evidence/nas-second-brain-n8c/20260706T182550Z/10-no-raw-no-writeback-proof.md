# 10 — No raw / no writeback proof (N8C-6)

## No vault / filesystem mutation
The four new pure modules perform **zero** filesystem writes:
```
$ grep -nE "write_text|open\(|\.write\(|shutil|os\.remove|unlink|mkdir" \
    context_pack_builder.py context_pack_repository.py enrichment_review.py context_pack_models.py
NONE
```
`context_pack_builder` reads content only through the N8C-3 DB-only path (`get_source_detail.text_excerpt`) and the derived review model — it never opens a vault file.

## Writes only the four context-pack tables
`ContextPackRepository` is the sole writer, and it writes only its own tables:
```
$ grep -oE "(INSERT INTO|UPDATE|DELETE FROM)\s+[a-z_]+" context_pack_repository.py | sort -u
INSERT INTO assistant_context_pack_events
INSERT INTO assistant_context_pack_items
INSERT INTO assistant_context_pack_receipts
INSERT INTO assistant_context_packs
UPDATE assistant_context_packs
```
No source / import / claim / enrichment table is written. Test `test_context_pack_builder.py::test_apply_persists_only_context_pack_tables` asserts every non-context-pack watched table row count is unchanged across `build --apply`.

## Preview / dry-run are read-only (clarification #5)
`test_context_pack_builder.py::test_preview_and_dry_run_are_read_only` snapshots row counts for `assistant_context_pack%`, `assistant_claim%`, `assistant_enrichment%`, and `source_intelligence%` tables before and after `preview_context_pack(...)` and `build_context_pack(..., apply=False)`, and asserts `before == after`.

## No raw prompt/response and no full result_json persisted
- Enrichment receipts (V101) already store only sha256 **digests** of the prompt/response, never the raw text — unchanged by N8C-6.
- A context-pack item stores only bounded `content_excerpt` / `evidence_excerpt` (capped by `context_pack_models`), and links the source enrichment output via `receipt_id` + `result_digest`. The string `result_json` appears in the new code only in **comments/docstrings**, never as a stored column value:
```
$ grep -n result_json assistant_context_pack_tables.py context_pack_repository.py context_pack_builder.py
# (only docstring/comment lines — no column named result_json, no value written)
```
- `test_context_pack_builder.py::test_items_never_store_full_result_json` and `::test_export_is_bounded_json` assert no `result_json` key is present in items or export.

## No raw email bodies
N8C-6 never reads `.eml` bytes or email bodies; its only content source is the bounded, redaction-safe indexed `text_excerpt` and model-summary excerpts. No email parsing path is imported.

## No startup builder / worker / scheduler
```
$ grep -rnE "context_pack|ContextPack" automation/ api.py | grep -iE "lifespan|startup|scheduler|BackgroundTask|watcher|auto"
NONE
```
The pack is built only by an explicit `hb-assistant context-pack build --apply` (or a direct service call). No lifespan/scheduler/watcher path enqueues or builds anything. (Mirrors the N8C-5 `test_enrichment_no_autostart` posture.)

## Candidate claims stay candidate/unreviewed
The builder and review model only READ claims (`get_claims_for_source`, `list_claims`); they never call `set_status`. `test_enrichment_review.py::test_review_items_from_claim_extraction_receipt_stay_candidate` asserts claims remain `status=candidate` / `review_state=unreviewed` after derivation.
