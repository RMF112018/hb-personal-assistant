# Phase B — Implementation Summary (Architecture Completion)

Non-production, local, review-ready. No production DB/NAS/watcher/deploy touched. Branch cut from
`origin/main` @ `77cf87da`.

## What Phase B delivers

A frontier-model client can now go **search result → stable `source_ref` → complete supported read**
with explicit trust/completeness semantics, while every Phase-A fail-closed guarantee is preserved.

| Sub-goal | Delivered |
|---|---|
| **B1** complete supported-file retrieval | `assistant_source_file_read(mode="complete")` returns a whole txt/md/csv/json/xml/html/log file, or a complete PDF/DOCX/XLSX/EML extraction; complete-or-explicit-failure (never a truncated "complete"). |
| **B2** parser process isolation | New `files/parsers/isolated.py`: each PDF/DOCX/XLSX/EML parse runs in a spawned, process-group-isolated child with input-size gate, memory rlimit, wall-clock timeout, and an output-byte budget. Parent survives timeout / segfault / OOM / malformed payload. |
| **B3** stable identity + provenance | `source_ref` is the preferred path-free handoff; cross-root/traversal/symlink/forged references fail closed; a path-free `provenance` block mirrors the authoritative top-level state fields. |
| **B4** rename/move lineage | V126 adds `renamed_from_source_id`; `apply_confirmed_same_root_move` links old→new in one transaction (no content-trust carry-forward); an old `source_ref` answers `moved` + successor; cross-root/unconfirmed moves stay conservative. |
| **B5** client semantics + manifest | Tool description + operating-manifest updated for `mode`, the state vocabulary, `source_ref` handoff, and honest XER/archive non-support. Isolated debt commit fixes the source-tool disambiguation guard. |

## State contract (centralized in `source_connector_models.py`)

`retrieval_state ∈ {complete, partial, unsupported_format, archive_not_expanded, too_large, unavailable,
denied, stale, moved, parser_timeout, parser_failed, parser_resource_exceeded, parser_output_too_large}`;
`content_state ∈ {raw_text, extracted_content, metadata_only, none}`;
`completeness_state ∈ {complete, partial, none}`. Invariant enforced in code: `retrieval_state==complete`
⇔ `completeness_state==complete`; `partial` is reserved for `mode="excerpt"`.

## Files created

| Path | Purpose |
|---|---|
| `src/hb_assistant/files/parsers/isolated.py` | Subprocess-isolated bounded parser supervisor (`extract_for_complete_read`). |
| `tests/test_source_file_complete_read.py` | Complete text reads, states, too_large, drift, provenance, mode validation, roundtrip. |
| `tests/test_source_file_parser_isolation.py` | Real PDF/DOCX/XLSX/EML parses + crash/timeout/oversize isolation, process-group grandchild kill. |
| `tests/test_source_file_retrieval_semantics.py` | XER/ZIP/unsupported/denied + identity fail-closed. |
| `tests/test_source_index_rename_lineage.py` | Transactional move, rollback, old-ref→moved ordering, watcher helper. |
| `tests/test_migrator_v126_rename_lineage.py` | V126 additive/idempotent/parity migration. |

## Files modified

| Path | Change |
|---|---|
| `obsidian_mcp/source_content_provider.py` | `mode`/`max_bytes`, complete-read cascade, drift guard, provenance, moved-resolution; excerpt path unchanged + state-annotated. |
| `obsidian_mcp/source_connector_models.py` | State-vocabulary constants + `COMPLETE_READ_TEXT_EXTS`. |
| `obsidian_mcp/source_connector_service.py` | `read_source_file` passes `mode`/`max_bytes`. |
| `obsidian_mcp/config.py` | Split input/output limits + parser timeout/memory. |
| `obsidian_mcp/source_watch.py` | `on_moved` → transactional same-root lineage via new testable `apply_same_root_move`; conservative fallback. |
| `obsidian_mcp/source_index_repository.py` | `apply_confirmed_same_root_move` (transactional) + `find_successor_source_id`. |
| `store/migrator.py` | V126 `renamed_from_source_id` (+ partial index); `LATEST_SCHEMA_VERSION`=126. |
| `nas_mcp/broker.py`, `nas_mcp/tool_registration.py` | `mode`/`max_bytes` passthrough; read/health/query_plan descriptions (disambiguation + complete-mode contract). |
| `docs/architecture/client-tool-operating-manifest.md` | File-access section: complete vs excerpt, states, `source_ref` handoff, XER/archive honesty. |
| `scripts/ci_source_index_gate.sh` | Added Phase B tests + latency test; removed the disambiguation deselect (now enforced); added `isolated.py` to lint. |
| `tests/test_source_index_quarantine.py` | Version literals `125` → `LATEST_SCHEMA_VERSION` (required by the V126 bump). |

## Isolation guarantee (tested OS + rlimit note)

Tested on **Darwin (macOS 27, arm64), CPython 3.14.5**. The hard crash/hang-isolation guarantees are
**subprocess wall-clock timeout → SIGTERM → SIGKILL → process-group reap** (a `setsid` process group,
proven by the grandchild-kill test). `RLIMIT_AS`/`RLIMIT_CPU` are applied before parser import as
best-effort defense-in-depth; on Darwin `RLIMIT_AS` enforcement is weak, so it is not relied on as the
primary bound. No network, OCR, archive expansion, or temp files are used.

## Migration recovery posture (V126)

Additive + nullable + parity-guarded (idempotent). A code rollback may leave the unused column in place;
no destructive down-migration is required in Phase B. A failed partial migration is safely rerunnable
(proven by `test_parity_guard_on_partially_migrated_db`). Production backup/restore/rollback-rehearsal
and schema-copy proof remain **Phase C** scope.
