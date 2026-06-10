# 08 — No-Leak and Security Proof

## Scans run
1. `hb-assistant procore analytics no-raw-leak-scan` over the evidence directory, the
   committed `projection_registry.json`, and the new projection source modules →
   `ok = true`, `unsafe_finding_count = 0`.
2. Staged/untracked artifact check: no `.sqlite`, `.db`, `.env`, `.payload`, `.pyc`,
   `__pycache__`, or raw `.json` payload dumps among the change set.
3. Pattern scan of `projection_registry.json` for signed-URL / bearer / access_token /
   SharedAccessSignature / PEM markers → none (the registry holds only field *names*,
   types, business categories, and destinations).
4. Registry entry-key audit: `path_map`/column entries contain only
   `{path, type, category, dest, rel, column}`; endpoint specs only
   `{endpoint_family, primary_table, primary_columns, child_tables, path_map, coverage}`.
   No payload values are present.

## Classification of detector posture
- Detector literals: the scrubber/no-leak regexes live in code constants only.
- Redacted examples: none required; evidence carries counts/paths/table names/hashes only.
- Real leaks: **none**.

## Structural guarantees
- Transport-secret exclusion reuses `AUTH_SECRET_KEY_RE`; the registry loader re-asserts
  that every transport-secret path is `exclude` and is never promoted to a column
  (defense in depth — registry and runtime scrubber cannot diverge).
- The projection engine emits no raw payload values to logs or receipts; receipts carry
  counts and field *names* only.
- Evidence files contain counts, field paths, table/column names, percentages, and hash
  prefixes only — no raw payload bodies, project text, URLs, tokens, or secrets.
