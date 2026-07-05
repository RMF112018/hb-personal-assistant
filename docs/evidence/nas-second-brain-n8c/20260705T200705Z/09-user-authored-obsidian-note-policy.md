# 09 — User-Authored Obsidian Note Policy

## Policy (enforced + seam)
User-authored vault notes are **raw/user-authored by default** (`source_kind="obsidian_note"`):
- may be indexed, summarized, linked, linted, and used for future Qwen jobs;
- **must not be freely rewritten** — any update goes through a controlled managed block / companion
  card / review-apply workflow;
- **must not be carded** as a generated source card, nor mistaken for one.

## Enforcement points
- `generate_source_card` already refuses `source_kind=="obsidian_note"` with
  `source_card_not_applicable` (`obsidian_mcp/source_notes.py`) — a user note is never carded.
- N8C-2 `classify_note` returns `user_authored` for a note with no decisive generated frontmatter and
  outside the generated folders — it is never `source_card`.
- `validate_card_frontmatter` fails a non-source-card note (`not_a_source_card:user_authored`).

## Proof
- `test_user_authored_note_not_classified_as_source_card` — a hand-written note (no frontmatter) →
  `user_authored`; `parse_source_card` returns `None`.
- `test_ai_outputs_card_not_classified_as_source_card` — AI-Outputs note → `ai_output`, not a source
  card (adjacent misclassification guard).

N8C-2 performs no write to any user note; the policy is read-only classification + the existing
generation refusal.
