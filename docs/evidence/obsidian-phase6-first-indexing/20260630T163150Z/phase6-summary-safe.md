# Phase 6 / 6B Summary (sanitized — counts only)

## Tooling
- `scripts/obsidian_source_first_indexing_apply.py`: single-root, deterministic, capped first
  production indexing via the DIRECT path index_source_file -> generate_source_card (no event queue;
  enqueues 0; never drains; post-apply asserts queued-event delta == 0). Selection reuses the Phase-5
  dry-run module (auto_card_high + domain work, sorted by rel_path).
- Phase 6B added stat-only readability detection (no forced downloads): `online_only_or_dataless`
  (st_size>0, st_blocks==0) skipped BEFORE any read; read-time failures caught per reason
  (read_timeout / read_permission_error / read_error). The loop walks the FULL high pool, skipping
  unreadable placeholders, generating up to the card cap. Preview mode = stat-only readable-vs-dataless
  view. Gates unchanged (confirm-*, backend-on-8000, require-empty-queue, root validation, caps,
  non-high/non-work/route refusals, max-summaries==0).
- 22 apply tests pass (gates, deterministic selection, routed generation + frontmatter/PM-sections +
  filename scheme, no-overwrite, no-unrelated-queue-drain, path-free summary, external-files-unmodified,
  and 6B: dataless/timeout/permission/read-error skipped + count-logged, selection-continues,
  pool-exhausted blocker, readability-status branches). 133 targeted tests pass overall; ruff clean.

## Dry-run (re-run, read-only)
- root syn-work, max_files=500, cap_reached=true; by disposition: auto_card_high=98,
  auto_card_normal=323, metadata_only=77, unsupported=2; all domain=work. Matches Phase 5.

## Production apply outcome (6B): 0 cards generated — pool exhausted (all candidates online-only)
- pool_size=98 (auto_card_high + work within the 500-file scan); readable_considered=0;
  generated=0; summaries=0; enqueued=0; errors=0; queued_event_delta=0.
- skips_by_reason: online_only_or_dataless=98, read_timeout=0, read_permission_error=0, read_error=0.
- pool_exhausted_before_cap=true (fewer than 25 readable high candidates within the 500-file cap).
- **Every** high-value candidate in syn-work's first 500 files is a cloud online-only placeholder
  (st_blocks=0, dataless). The placeholder-skip ran fast with no read timeouts (vs Phase 6's 25
  TimeoutErrors). Per the rules, did NOT expand caps / force-download / cherry-pick.
- **Zero writes:** generated_notes unchanged (67 not_generated); 0 syn-work source rows; queue 0/0;
  Source Notes/Work has only its pre-existing README.

## Runtime status (read-only, one backend, current code)
- queue 0/0/0, generated 0, stale 0; watcher running, watchdog, degraded false, is_owner true; backend
  started once and stopped at closeout; port 8000 clear.

## Confirmations
- No all-root scan; no unrelated queue drain; no broad summaries (0); one backend only, stopped.
- Quarantine not deleted/copied; external roots untouched (only stat-based readability checks; dataless
  files were never read, so no downloads triggered). Sensitive evidence kept local/untracked; only
  count-only summary committed.

## Blocker + recommended next
- To generate the first real cards, the operator must MATERIALIZE (make-available-offline) the target
  high-value files in the cloud drive for syn-work, then re-run the apply (no code change needed); OR
  authorize scanning deeper than 500 files / a different root, where materialized high-value files may
  exist. The tooling is complete, fast, and placeholder-aware; the only blocker is data materialization.
