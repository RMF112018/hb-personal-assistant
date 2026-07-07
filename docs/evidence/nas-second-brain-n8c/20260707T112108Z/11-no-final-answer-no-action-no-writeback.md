# 11 — No Final Answer / No Action / No Live Source Read / No Writeback

**Finality proof.** Grep for `final_answer|answer_text|generated_answer|operator_approved_answer|
authoritative_answer|send_answer|generate_answer` across all new + changed SOURCE returns matches ONLY inside
docstrings/comments that DOCUMENT the absence of those names (in `answer_draft_builder.py`,
`answer_draft_models.py`, `assistant_answer_draft_tables.py`, `migrator.py`) — never a field, column,
variable, or tool. `test_answer_draft_v108_migration.py::test_no_finality_columns_on_draft_tables` asserts no
such column on any of the 5 tables; `test_answer_draft_builder.py::test_no_finality_fields_and_preview_is_read_only`
asserts no such key in the built payload; API `_assert_safe` needles include them.

**No live source file read during drafting (clarification #7).** The builder imports only
`source_connector_models.encode_source_ref` (pure) and calls `source_repo.get_source_detail` (DB read). It
never imports/calls `SourceContentProvider` / `source_file_read` / `read_source_content`. Grep for those in
the new source returns nothing. `test_answer_draft_builder.py::test_no_live_source_file_read_during_drafting`
monkeypatches every live-read entrypoint on `source_content_provider` to raise, then builds a draft with a
real `SourceIndexRepository` — the build succeeds without triggering any of them.

**No action / no writeback.** No action/email/calendar/task/reminder/notification/bridge path; no vault or
source/card mutation; the remote MCP surface exposes no write/build/answer/action tool; the RO snapshot is
physically read-only (`test_nas_mcp_answer_drafts.py::test_snapshot_is_read_only`). No raw prompt/response or
email body is persisted — sections/citations store only bounded restatements + ids/digests/state/refs.
