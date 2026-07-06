# Stale / Ambiguous / Deleted Source Handling

At completion the worker re-validates the subject (DB-only, no vault read) via
`_subject_stale_reason`: re-reads `get_source_detail`; if `None`/`deleted` -> `source_deleted`; if the
enqueue `source_digest` != current `content_sha256` -> `source_digest_drift`; if a note-anchored job's
`get_source_for_card` resolves `ambiguous` -> `ambiguous_source_card_link`.

On any adverse verdict the job is `stale`, receipt `applied_status=stale_rejected`, and NOTHING is
ingested. Proven:
- `test_source_digest_drift_marks_stale_no_ingest` (re-index bumps content_sha256 -> drift),
- `test_deleted_source_marks_stale` (`mark_deleted`),
- `test_ambiguous_card_link_marks_stale`.
Oversized/malformed model output fails safely (receipt `failed`), never truncated-and-ingested
(`test_oversized_output_fails_no_ingest`, plus pure `parse_result` validators).
