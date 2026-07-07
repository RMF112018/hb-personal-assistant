# N8C-21 — source-connector read smoke

The source-connector group (N8C-12) stays read-only and indexed-only: it discovers/reads indexed NAS source
files via opaque `source_ref`s and never performs a live filesystem scan of a sensitive root. The local smoke
dispatches `assistant_source_roots_list` over the temp DB and asserts `ok` (`05b-smoke-output.txt`).

No `source_file_read` / `SourceContentProvider` / source scan-reindex / source-card generation path is exercised
or exposed — consistent with the N8C boundary. Deeper behavioural coverage lives in the N8C-12 source-connector
test suite (unchanged by this phase).
