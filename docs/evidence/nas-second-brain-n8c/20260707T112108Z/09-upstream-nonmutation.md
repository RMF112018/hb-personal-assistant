# 09 — Upstream Non-Mutation

The draft layer writes ONLY the 5 `assistant_answer_draft*` tables. It never mutates a packet, projection,
review, source-advisory, source-index, vault, or import record.

- `AnswerDraftRepository.upsert_draft` inserts into the 5 draft tables only; supersede/stale writes touch only
  the draft header + draft events.
- Proof: `test_answer_draft_repository.py::test_upsert_writes_only_draft_tables` snapshots
  `assistant_research_packets` / `_items` / `_citations` / `source_intelligence_sources` before and after a
  build+apply and asserts byte-identical row digests.
- Source enrichment is a READ: `get_source_detail` (DB row) + `encode_source_ref` (pure). No write, no file
  read (see 11).
- `preview` / `build --dry-run` persist nothing (`test_no_finality_fields_and_preview_is_read_only`).
