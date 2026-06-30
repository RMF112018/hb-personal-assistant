# Runbook — Bounded First Source-Indexing Pass

A controlled, **operator-approved** first indexing pass over a **single** external source root, under
explicit caps. This runbook is preparation only — running it is a separate, explicitly authorized
action. **Phase 4 does NOT run any indexing.**

## 1. Purpose
Generate the first batch of PM-grade source cards from ONE enabled source root, bounded by hard caps,
so output is reviewable before any broader indexing. Never a broad rescan of all roots.

## 2. Preconditions
- On latest `origin/main`; clean worktree.
- Watcher single-owner lease healthy (fail-closed); `degraded: false` when a backend runs.
- Active vault is the clean Work/Home vault; stale pre-reset generated-note rows already retired
  (Phase 4 → all `not_generated`).
- Backend stopped before any preflight; only ONE backend ever started.

## 3. Root selection
- Exactly ONE `source_root_key` (e.g. `syn-work`). All other roots stay disabled for the pass.
- Record the chosen key explicitly in the evidence package.

## 4. Queue/status preflight (read-only)
- `source_intelligence_events`: **queued and processing must both be 0** (hard stop otherwise).
- Capture `generated_card_count` / `stale_note_count` / `skipped_by_code` before.

## 5. Candidate dry-run
- Enumerate candidate files under the single root (bounded by `external_source_scan_max_files`).
- Produce candidate counts **by disposition** (auto_card_high / auto_card_normal / metadata_only /
  deferred / excluded / unsupported) WITHOUT indexing.
- Keep any path-bearing candidate report LOCAL/untracked.

## 6. Apply authorization
- Operator reviews the dry-run disposition counts and explicitly approves before any enqueue/drain.
- No enqueue, no drain, no card/summary generation without that approval.

## 7. Max caps (all explicit; refuse to exceed)
- `max_events` — cap the enqueued event count for the pass.
- `source_card_auto_max_per_drain` (cards/drain) and `source_summary_auto_max_per_drain`
  (summaries/drain) bound generation.
- Single root only; no cross-root fan-out.

## 8. Stop / rollback
- Stop the backend to halt the watcher/drain at any time.
- Generated cards live under `Source Notes/…`; retire them via the generated-note retirement tool
  (status → `not_generated`) — never delete external source files.
- No schema changes; no external-root mutation.

## 9. Evidence package
- Preflight queue/status, chosen root key, dry-run disposition counts (count-only safe summary), the
  approval record, post-pass counts, and a backend start/stop log. Path-bearing artifacts stay local.

## 10. Explicit non-goals
- **No broad rescan**; **no all-root indexing**; **no CPM import** (schedules classify only);
  **no external file mutation**; **no source-root deletion**; **no manual production queue drain**
  outside the approved capped pass.
