# Phase 6 Summary (sanitized — counts only)

## Bounded first-indexing apply tool
- New `scripts/obsidian_source_first_indexing_apply.py`: single-root, deterministic, capped first
  production indexing via the DIRECT path `index_source_file` -> `generate_source_card`
  (no event queue: enqueues 0, never drains, never claims unrelated queued events). Selection reuses
  the Phase-5 dry-run module (`scan_root`) so it is identical to the read-only preview: keeps only
  `auto_card_high` + domain `work`, sorts by rel_path, caps at 25.
- Apply gates (all enforced + tested): requires `--apply` + exact confirm-root/db/vault; refuses if a
  backend listens on 8000; refuses nonzero queued/processing (require-empty-queue); refuses disabled/
  missing/unmounted/in-vault/quarantine root; caps selection; refuses non-high / non-work / not-under-
  `Source Notes/Work/`; never overwrites user files; `--max-summaries` must be 0. Post-apply asserts
  queued-event delta == 0.
- 16 apply tests pass (incl. generated cards land under Source Notes/Work with basename+id12 filename,
  domain/disposition/confidence/review_status/template/card_version frontmatter + PM body sections,
  no source-dir replication, no user-file overwrite, no unrelated-queue drain, path-free safe summary,
  external files unmodified). 168 targeted tests pass overall; ruff clean.

## Dry-run (re-run, read-only)
- root_key=syn-work, max_files=500, cap_reached=true; by disposition: auto_card_high=98,
  auto_card_normal=323, metadata_only=77, unsupported=2; all domain=work. Matches Phase 5 exactly.

## Production apply outcome: 0 cards generated — BLOCKED by online-only source files
- selected=25 (auto_card_high, work, deterministic), enqueued=0, processed=0, generated=0,
  summaries=0, skipped=0, **error=25 (all TimeoutError)**, queued_event_delta=0.
- Root cause: the first 25 deterministically-selected syn-work candidates are **cloud "online-only"
  placeholders** (logical size present, `st_blocks=0`, dataless); reading them to extract text times
  out. Confirmed: a 5s read of the first file timed out; stat shows 0 allocated blocks.
- **Zero writes:** generated_notes still 67 not_generated; 0 syn-work source rows created; queue 0/0;
  Source Notes/Work has only its pre-existing README (no cards). The apply is atomic per file and left
  the DB + vault unchanged.
- Per the rules, did NOT cherry-pick different/materialized files, change caps, or force-download.

## Runtime status (read-only, one backend, current code)
- queue 0/0/0, generated 0, stale 0; watcher running, mode watchdog, degraded false, is_owner true;
  backend started once and stopped at closeout; port 8000 clear.

## Confirmations
- No all-root scan; no manual unrelated queue drain; no broad summaries (0). One backend only, stopped.
- Quarantine not deleted/copied; external roots untouched (read attempts only; nothing modified).
- Sensitive evidence (apply/dry-run detail with rel paths, db baseline) kept local/untracked; only
  count-only summaries committed.

## Recommended next
- Materialize the target syn-work files locally (cloud-drive "make available offline") for the
  selected set, OR authorize a follow-up that (a) skips online-only/dataless files during selection and (b)
  selects the next readable auto_card_high candidates under the same caps — then re-run the apply.
