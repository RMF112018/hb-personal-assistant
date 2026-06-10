# Repo-Truth Audit — Follow-up Watch Quality (Prompt 03)

## Existing surfaces

| Concern | Location | State |
|---|---|---|
| Watch classifier | `…/local_ai/follow_up_watch.py` `classify_watch_status` | Deterministic (no clock read), 6 statuses: open / waiting_on_me / waiting_on_others / possibly_resolved / stale / closed. First-match precedence; reason codes + signal type. |
| Scan + persist | `run_follow_up_watch_scan` | Dry-run default; `--apply` requires `--max-persist` cap; source-ref gate (no refs → never persisted); unchanged-skip; writes `follow_up_watch_items` + `follow_up_status_events` (13 guard columns each). |
| CLI | `follow-up-watch scan` / `enrich` | scan = deterministic; enrich = optional V45 raw enrichment (fail-closed). |
| V45 pending section | Prompt 01 | Brief surfaces model-enriched email follow-ups (separate source). |

## Gaps (Prompt requirements 2 + 4)

1. The classifier produces a watch *status*, but there was no surface mapping items to **operator
   actions**, and no explicit **needs-review / insufficient-evidence / not-actionable** bucket.
2. Quality gates existed only as the persist-time source-ref gate; there was no advisory surface
   showing *why* an item is non-actionable (no source ref, or contradictory signals).

## Decision (surgical)

- Add deterministic quality gates + operator-action mapping + a report builder/renderer to
  `follow_up_watch.py` (`watch_quality_flags`, `operator_action_for`,
  `build_follow_up_watch_report`, `render_follow_up_watch_report_markdown`).
- Add `second-brain follow-up-watch report` (read-only, deterministic, JSON/Markdown).
- Quality gates: no source ref → `insufficient_evidence` → needs-review (non-actionable);
  terminal status + active waiting + no completion → `contradictory` → needs-review. Stale threshold
  remains the explicit `--stale-after-days` (default 14).
- No new brief section — the watch report is its own CLI surface; it complements (does not duplicate)
  the Prompt 01 V45 pending section. No schema change, no model, no writeback.
