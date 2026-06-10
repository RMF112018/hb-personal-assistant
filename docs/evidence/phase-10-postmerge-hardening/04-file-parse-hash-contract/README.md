# 04 — Clarify File Parse Hash Contract

## Goal
Stop the file-parse read-model from implying full-text hashing. The hash covers the parser's
**bounded `text_excerpt`**, so the field is renamed and an explicit scope is added.

## Change (`local_ai/file_parse_read_model.py`)
- `text_hash` → `text_excerpt_hash`; added `hash_scope: "text_excerpt"` to every record
  (parsed / degraded / unsupported / error).
- Docstring now states the hash covers the bounded excerpt (with repo-truth citation).
- `render_file_index_markdown`: `hash:` → `excerpt-hash:`.
- `src/hb_assistant/cli/files.py`: help/docstring tightened to "sha256 of the bounded excerpt".
- No deprecated alias kept (new Phase 10 surface; only consumer is the CLI builder call).

## Evidence updated
Phase 09 captured outputs that named the field were updated in place (rename + `hash_scope`,
authentic hash values preserved): `09-document-file-parsing/{01,02,03,04,05,06,08}`.

## Proof
- `hash-contract-proof.md` — exactly what is hashed + bounded-excerpt repo-truth + consumer proof.
- `final-output.json` / `final-output.md` — live CLI capture showing `text_excerpt_hash` +
  `hash_scope` (JSON) and `excerpt-hash:` (Markdown).

## Test
`tests/test_phase_10_file_parse_read_model.py` updated: asserts `hash_scope == "text_excerpt"`,
`text_excerpt_hash` shape, and `"text_hash" not in rm`.
