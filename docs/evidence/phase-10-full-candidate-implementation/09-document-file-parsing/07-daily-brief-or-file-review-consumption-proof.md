# File-review consumption proof (metadata-only, no unreviewed interpretation as fact)

The review-safe file read-model is a **metadata-only** index (id, name, extension, MIME, parsed status, extraction method, text length + hash, counts, degraded reason). It can feed a file-review surface or the daily brief safely because:

- it carries **no extracted text** and no document interpretation — so nothing unreviewed is presented as fact;
- it is deterministic, local-only, and source-linked (file id + optional source refs);
- degraded/unsupported files are reported honestly rather than silently dropped.

- example index counts: {'files': 6, 'by_status': {'parsed': 4, 'degraded': 1, 'unsupported': 1}, 'by_extension': {'.txt': 1, '.md': 1, '.docx': 1, '.xlsx': 1, '.pdf': 1, '.xyz': 1}}
