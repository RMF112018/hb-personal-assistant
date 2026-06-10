# Repo-Truth Audit — Candidate Review UX (Prompt 02)

## Existing surfaces (mature)

| Concern | Location | State |
|---|---|---|
| Review service layer | `…/local_ai/candidate_review.py` | `review_summary`, `list_review_candidates`, `show_review_candidate`, `accept/reject/ignore/snooze/edit`, `export_review_queue` — pure, local-DB only, raw-free. |
| Review CLI group | `cli/second_brain.py` `review_app` | `policy-status`, `burden`, `queue`, `clusters`, `list`, `show`, `summary`, `accept`, `ignore`, `reject`, `snooze`, `edit`, `export`. |
| Batch apply + cap | `_run_review_batch` | Dry-run by default; `--apply` persists; `--max-actions` caps (`ids[:max_actions]`, `skipped_over_cap`). This is the bounded-cap apply guard. |
| Candidate tables | `task_candidates` / `commitment_candidates` (V41) + V43 lifecycle cols + 13 P10 guard columns | Redacted fields only. |
| Source refs | `candidate_source_refs` | Read-only, immutable in review ops. |
| Promotion | `store.promote_task_candidate` → `accepted_tasks` | Exists in store; intentionally NOT exposed as a new CLI apply here (avoid speculative scope). |

## Gap (Prompt requirement 3)

The building blocks existed (counts via `summary`, rows via `list`, JSON via `export`) but there was
**no single legible operator-facing report** that shows the full lifecycle at once — what is pending /
accepted / rejected / snoozed / suppressed, what needs Bobby's review, what a bounded apply would act
on — each item source-linked with confidence/safety reasons.

## Decision (surgical)

Add one read-only/dry-run surface that composes the existing primitives:
- `build_review_report()` + `render_review_report_markdown()` in `candidate_review.py`.
- `second-brain review report` CLI verb (JSON default; `--no-json` prints Markdown; `--markdown-out`
  writes it; `--apply-cap` bounds the dry-run preview-apply set).

No parallel CLI, no new persistence path, no schema change. All existing review verbs unchanged.
Dry-run/read-only by design; the existing `review accept … --apply --max-actions` remains the
bounded apply.
