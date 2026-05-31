# Phase 07B Prompt 07 — Email Thread Summary Materialization: Proof (redacted)

Date: 2026-05-31 · Branch: `main` · Repo SHA at start: `8aeb36d` · Package `1.3.0` ·
Schema head V23 · Thread-summary policy `phase07b-email-thread-summary-policy-v1`.

Adds `EmailThreadSummaryMaterializer` (local-only, Graph-free) that groups indexed,
project-matched email by `thread_key` into **metadata-only** redacted thread summaries,
routes sensitive/high-impact threads to human review, and records an auditable run. All
values below are structural facts only — no UPN, tenant GUID, scopes, file paths, raw
subjects, raw email addresses, URLs, or body content.

## Files changed

- `src/hb_assistant/construction/email/thread_summary.py` (new — materializer + Pydantic
  `ThreadSummaryReport`/`ThreadSummarySample`)
- `src/hb_assistant/construction/store/repositories.py` (`get_email_thread_summary`,
  `list_email_thread_summaries`, `insert_/complete_email_thread_summary_materialization_run`)
- `src/hb_assistant/cli/graph.py` (`graph mail thread-summary` command + imports)
- `src/hb_assistant/construction/email/__init__.py` (exports)
- `tests/test_email_thread_summary.py` (new — 6 tests)
- `docs/architecture/24-phase-07b-email-thread-summary.md` (new)
- this evidence file

## Preflight (HEAD 8aeb36d, all exit 0)

`git status --short` (clean except untracked `.claude/`), `python -m compileall -q src tests`,
`ruff check .` (All checks passed!), `mypy src` (Success), `pytest -m "not live and not
integration and not manual"` (0 failed).

## Post-implementation local validation (all exit 0)

| Command | Result |
| --- | --- |
| `python -m compileall -q src tests` | exit 0 |
| `ruff check .` | All checks passed! |
| `mypy src` | Success: no issues found in 159 source files |
| `pytest tests/test_email_thread_summary.py -v` | 6 passed |
| `pytest -m "not live and not integration and not manual"` | 0 failed |
| `pytest tests/test_mutation_lockout.py` | passed (graph/ static no-write scan clean) |
| `hb-assistant construction-agent validate --json` | exit 0 |
| `hb-assistant procore validate --json` | exit 0 |
| `hb-assistant graph files status --json` | exit 0 |
| `hb-assistant graph mail status --json` | exit 0 |
| `hb-assistant graph calendar status --json` | exit 0 |
| `hb-assistant graph mail thread-summary --json` (dry-run default) | exit 0 |
| `hb-assistant construction-agent data-quality gates --json` | exit 0 |
| `hb-assistant construction-agent data-quality no-writeback-proof --json` | proof_passed=true |

`ruff format` is NOT enforced repo-wide (222/341 files would reformat); `ruff check .` is the
authoritative lint gate and passes. `ruff format` was intentionally not run.

The 6 unit tests cover: metadata-only persistence + idempotent upsert; dry-run persists
nothing (summaries + review queue + runs all 0); sensitive thread routes to review without
leaking the raw preview token; run receipt recorded with all guard columns 0; the controlled
body-context policy (a sensitivity term present only in the encrypted body routes to review
**only** when both the flag and the policy allow it, and the secret body token never appears
in the summary, report, review queue, or the raw SQLite file); and get/list round-trip.

## Live real-store proof (Graph-free)

`hb-assistant graph mail thread-summary --project tropical --lookback-days 366 --no-dry-run
--json` against the real local store:

| Metric | Value |
| --- | --- |
| threads_considered | 19 |
| threads_summarized | 19 |
| review_required_count | 2 |
| persisted | true |
| encrypted_body_context_used_count | 0 (default policy disallows body context) |
| summary_mode | metadata_only |

Read-only SQL verification over the real tables:

```
email_thread_summaries: 19 rows (2 review_required)
email_thread_summary_materialization_runs: 1 row
run receipt → status=completed, threads_summarized=19, review_required_count=2,
  raw_body_persisted=0, raw_prompt_persisted=0, raw_response_persisted=0,
  external_writeback_performed=0
leak scan: 0 summaries contain '@' or 'http'; 0 participants_hash_json contain '@'
distinct summary_policy = metadata_only
sample summary_redacted = "thread: 1 message(s), 1 participant(s); window <ts> -> <ts>"
```

- **Idempotency:** re-running the same apply summarized 19 and left the row count at **19**
  (upsert keyed on `thread_key`).
- `no-writeback-proof --json` after the live write → `proof_passed=true`,
  `no_raw_values_persisted=true`.
- `pytest tests/test_mutation_lockout.py` after the change → still clean.

## Scope notes

- No Microsoft 365 mutation/writeback; mailbox read-only; no Phase 07D meeting-prep readiness
  is claimed.
- The no-writeback / no-raw-body prover still scans only the Phase 07A V20/V21 tables;
  extending it to the V11/V23 email-thread and V14 classification tables is deferred to
  Phase 07B Prompt 12.
