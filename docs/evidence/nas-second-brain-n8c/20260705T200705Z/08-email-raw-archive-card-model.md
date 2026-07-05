# 08 — Email Raw / Archive / Card Model

Three surfaces preserved and kept distinct; N8C-2 adds no `.eml` parser and blocks no future one.

1. **Raw `.eml`** — immutable original, indexed as `source_kind="external_file"`
   (`eml_file_source_id = source_id_for("external_file", source_root_key, rel_path)`).
2. **Readable Email Archive note** — `note_type: email_archive` + `source_type: eml` under
   `Email Archive/<Domain>/` (`obsidian_mcp/source_email_archive.py`, `is_email_archive_path`). Full
   body / addresses / message-ids live **only** here.
3. **Source/summary card** — a `note_type: source_card` note carrying the graph-safe managed `hb-email`
   block (hashed message-id, participant **domains**/**count**), so connected agents navigate email
   **without reading raw bodies by default**. Attachments: `Email Archive/…/Attachments/`
   (`is_attachments_path`).

## Classifier seam (`classify_note`)
- `note_type: email_archive` or `source_type: eml` → `email_archive` (never a source card).
- Attachments path under `Email Archive/` → `email_attachment`.
- The email's source **card** is a normal `source_card` (the `hb-email` block is content, not a type).

## Proof
- `test_email_archive_note_not_classified_as_source_card` — archive note → `email_archive`;
  `parse_source_card` returns `None`.
- Existing regression `test_obsidian_source_index_eml_archive.py`
  (`test_archive_notes_are_not_cards_and_protected_from_self_index`) stays green.

Seams for later slices (documented, not built): `eml_file_source_id`, `email_db_record_source_id`
(link source `email` kind), `email_archive_note`, `email_summary_card`. Redaction: no raw addresses,
bodies, or message-ids are surfaced by the identity layer.
