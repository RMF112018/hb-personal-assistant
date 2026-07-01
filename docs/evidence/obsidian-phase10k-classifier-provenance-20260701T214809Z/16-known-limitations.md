# Phase 10K — Known limitations

- **Scope is three families.** Only value-analysis logs, generic specification templates, and
  clarification/question memos are repaired. Other misclassifications are out of scope (deferred to
  Phase 10L). The guard refuses to overwrite any confident, unrelated type.
- **15 review_required cards in the Tropical corpus.** The bounded dry-run over 103 generated cards
  found 3 hard-conflict repairs and 15 cards with a *weak* family hint but insufficient excerpt
  evidence. These are left unchanged and counted `review_required` — candidates for an operator review
  queue in 10L, not auto-repaired here.
- **Bare-numeric filenames.** A memo whose source filename is purely numeric (e.g. `1.docx`) can be
  classified `drawing` by the sheet-number heuristic at index time; the guarded `from_detail` wire-in
  will not repair `drawing` (not in the memo conflict set). The card-level repair still works because it
  keys off the card's stored `scope_of_work`/etc. type + excerpt structure. Broadening the born-correct
  path for such filenames is future work.
- **Summary refresh is not performed.** If a generated summary still asserts the old type, the card is
  SKIPPED (`summary_refresh_required`) rather than repaired — 10K never edits summary text. Re-running
  the 10J summary path (or a future combined pass) would clear such skips. (None occurred for the 3
  target cards; their 10J summaries were already consistent.)
- **document_type provenance is not a DB column.** It remains derived; the repair persists provenance
  in the card (type + tag + Source Basis reason line), not in SQLite. A durable provenance column is
  future work.
- **No summary/tagging/backlink automation** is triggered by a repair; downstream re-tagging beyond the
  `source/type/*` swap is out of scope.
