# 229. Phase 10A — Candidate review targeted test suite (consolidation)

Date: 2026-06-08

Package: HB Construction Intelligence — Phase 10A Candidate Review CLI Implementation Package (repo-truth update)

## Context

Prompts 02–06 each shipped tests with their code, so the candidate-review feature
already carried 35 tests. This record finalizes the **full targeted suite** the
package's validation command names:

```
pytest tests/test_phase_10a_candidate_review.py tests/test_phase_10a_candidate_review_cli.py
```

Two adjustments were required.

## Decision

### Rename to the package-expected CLI test filename
`git mv tests/test_phase_10a_review_cli.py
tests/test_phase_10a_candidate_review_cli.py` so the validation command resolves
and the CLI file reads as the sibling of `test_phase_10a_candidate_review.py`. The
17 CLI tests are unchanged. The bare filename references in records 226/227/228
("Verified" sections) were updated to the new path so they stay runnable; their
per-run test counts are left as accurate snapshots of those prompts.

### Close the three uncovered required groups
Added to `tests/test_phase_10a_candidate_review.py` (service/store level — the CLI
verbs route through these same paths):
- **`test_list_sorting_by_created_utc_desc`** — sets distinct `created_utc` via
  direct SQL (the upsert stamps a colliding `CURRENT_TIMESTAMP`) and asserts
  `list_task_candidates` returns newest-first.
- **`test_snooze_visibility_in_list_and_summary`** — a snoozed candidate surfaces
  under `list_review_candidates(status="snoozed")` and in
  `review_summary(...)["combined"]["snoozed"]`, with `snoozed_until_utc` set.
- **`test_guardrail_columns_stay_zero_after_review_ops`** — after accept + edit +
  snooze (row updates + audit inserts), the 13 `PHASE_10_GUARD_COLUMNS` sum to 0
  across `task_candidates`, `commitment_candidates`, and `candidate_review_events`
  (reusing the `COALESCE(SUM(...))` idiom from `local_ai/schema.py`).

## Required-group coverage map

| Required group | Covered by |
|---|---|
| list filters + sorting | `test_list_and_status_filter_and_enum_reject`, `test_store_list_review_candidates_merge_and_filters`, **`test_list_sorting_by_created_utc_desc`** |
| show detail + source refs | `test_show_found_and_not_found_with_source_refs`, `test_review_show_cli_found_and_not_found` |
| accept/ignore/reject transitions | `test_accept_*`/`test_reject_*`/`test_ignore_*` (service + CLI) |
| snooze visibility | `test_snooze_persists_*`, **`test_snooze_visibility_in_list_and_summary`**, `test_review_snooze_cli_*` |
| edit audit changes | `test_edit_updates_fields_records_diff_*`, `test_review_edit_cli_records_changes_*` |
| export redaction | `test_export_returns_safe_items_*`, `test_review_export_cli_to_file_and_stdout`, no-forbidden-key guards |
| summary grouping | `test_summary_counts`, `test_review_summary_cli` |
| CLI error handling | invalid status → 2, not found → 3, mutually-exclusive / missing input → 2, bad `--until` → 2, `no_edits` → 2 |
| guardrail columns stay zero | **`test_guardrail_columns_stay_zero_after_review_ops`** |

## Verified

`pytest tests/test_phase_10a_candidate_review.py
tests/test_phase_10a_candidate_review_cli.py` → **38 passed** (21 service/store +
17 CLI). `ruff` clean. No stale references to the old filename remain in
`docs/`, `src/`, or `tests/`; the old file is removed.

## Guardrails / non-goals

Tests only — no production code change (no service/store/CLI/migration edits). No
extraction prompt/model/stable-key change; no packet-scope broadening. The new
tests assert existing guardrails (local-only writes, source-ref immutability, zero
guard columns, no raw output) and introduce no email/calendar/Graph/Procore/
external writeback and no raw content.
