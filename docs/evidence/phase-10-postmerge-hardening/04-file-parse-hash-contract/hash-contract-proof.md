# Hash Contract Proof — `text_excerpt_hash` / `hash_scope`

## What exactly is hashed
`build_file_parse_read_model` computes:
```
excerpt = str(result.get("text_excerpt") or "")
text_excerpt_hash = "sha256:" + sha256(excerpt.encode("utf-8","replace")).hexdigest()  # if excerpt else None
```
So the hash is **sha256 over the parser's `text_excerpt`** — and that excerpt is **BOUNDED** by the
parsers, not the full extracted document text.

## Repo-truth proof that `text_excerpt` is bounded (not full text)
- `files/parsers/txt.py`:  `excerpt = text[:max_chars]` → `char_count = len(excerpt)`
- `files/parsers/pdf.py`:  `_MAX_PAGES = 5` ("never the whole document"); `excerpt = "\n".join(parts)[:max_chars]`
- `files/parsers/docx.py`: `excerpt = "\n".join(parts)[:max_chars]`
- (xlsx/pptx/csv parsers are likewise bounded.)
- In every parser `char_count == len(excerpt)`, i.e. the read-model's `text_length` is the EXCERPT
  length, not the full-document length.

Conclusion: the field was previously named `text_hash`, which falsely implied a full extracted-text
hash. It now emits `text_excerpt_hash` with `hash_scope: "text_excerpt"` to make the scope explicit.

## Field rename (no alias)
- Emitted JSON key: `text_hash` → `text_excerpt_hash`; added `hash_scope: "text_excerpt"`.
- Markdown: `hash:` → `excerpt-hash:`.
- No deprecated `text_hash` alias is kept.

## Downstream-consumer proof (correction 4)
`grep -rn "text_hash" src tests | grep -iE "file_parse|parse_index|parse-index|file_index"` returns
only the negative-assertion test line (`assert "text_hash" not in rm`). The sole caller of the
read-model builders/renderer is `src/hb_assistant/cli/files.py`, which references the builder/renderer
functions, not the field name. No downstream consumer expects `text_hash` from this read model.

Out of scope (different fields, intentionally untouched): `text_hash` in
`store/procore_enrichment.py` / `store/procore_history.py` (Procore enrichment columns) and
`input_context_hash` in the reasoning/model-receipt code — these are unrelated symbols.
