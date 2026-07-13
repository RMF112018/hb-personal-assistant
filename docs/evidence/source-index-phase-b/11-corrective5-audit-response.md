# Phase B — Fifth Corrective Audit Response (PB-010 residual: no moved event reaches the unguarded fallback)

The AEOS focused review of the fourth round VERIFIED FIXED PB-012 and confirmed C4's core PB-010 atomicity
fix, but held **PB-010 OPEN** for one residual escape route: when an ownership-guarded terminal transition
itself raised a **non-busy** exception, a moved event escaped to `drain_queue`'s generic
`except Exception → repo.complete_event(event_id, "error", …)` fallback, which updates by `event_id` only
(no `status='processing' AND attempts=?` guard). A stale attempt could thus overwrite the current owner's
queue state.

This work lands as two immutable commits on `phase-b-source-index-architecture-completion`, preserving
`80b4d13d`, `e488136f`, `0464e347`, `5aeb7ab3` (C4), `8003ca02` (E5) — no amend:
- **C6** = `3f4a9b2b` — the code + tests only.
- **E5→...→E7** = this evidence-only commit, referencing `tested_code_sha = C6`.

**No push / PR / deploy / prod DB / watcher activation / prod migration.**

## FIND-PB-010 residual — every moved terminal route is attempt-generation guarded, no unguarded fallback

**Root cause (confirmed against repo truth).** Three escape routes all sit inside the per-event `try:`
(`source_indexer.py:2630`) that the generic handler catches: `_apply_moved_event`'s guarded completion
(1489), the `moved_invalid` branch (2742), and the `unconfigured_root` branch (2749). If any guarded
`complete_owned_event` raised a non-busy exception, control reached the generic
`except Exception → complete_event(event_id, …)` — the unguarded, event_id-only path.

**Fix** (`source_indexer.py`, one structural change at the generic drain handler; **fail-closed on the
claim generation**):
- A moved event in the generic handler is routed to an **attempt-generation-guarded** `complete_owned_event`
  **only** when `event["attempts"]` is a **verified positive int** (`type(x) is not int` rejects bool and
  str — no coercion; `< 1` rejects 0/negative; **no default attempt is invented**).
- If the guarded terminal write itself raises, or the generation is invalid, the event is left `processing`
  for `requeue_stuck` (fail-closed) with **sanitized** logging (event_id, attempt, exception class only — no
  paths, exception messages, or payload).
- **No moved event ever reaches the event_id-only `complete_event` fallback.** `_apply_moved_event`'s inner
  guarded completion is unchanged (the common success path never reaches the generic handler).

**Tests** (`tests/test_source_index_moved_drain.py`):
- `test_moved_guarded_terminal_failure_never_reaches_unguarded_fallback` — the full escape sequence:
  attempt 1 mid-flight → a concurrent reclaim bumps to **attempt 2** → the move raises non-busy → the inner
  guarded terminalization raises non-busy → the generic backstop retries the **guarded** completion. Asserts
  the backstop was reached (≥2 `complete_owned_event` calls), **every** call used `expected_attempt=1` and
  **none** used 2, `complete_event` was **never** called, the row stays **`(processing, 2)`** (attempt 2
  authoritative), and the stale attempt mutated no source/lineage. Recovers via deterministic
  `requeue_stuck`.
- `test_moved_invalid_terminalization_failure_reaches_backstop` and
  `test_unconfigured_moved_terminalization_failure_reaches_backstop` — the `moved_invalid` and
  `unconfigured_root` branches' guarded terminalization raise non-busy → the backstop catches (guarded
  retry, claimed attempt only), `complete_event` never called, event left `processing`, recoverable.
- `test_moved_backstop_invalid_claim_generation_fails_closed` — parametrized over
  **missing / None / 0 / negative / nonnumeric string / boolean**: an invalid claim generation reaching the
  backstop performs **no** queue mutation (neither guarded nor unguarded completion — no fabricated attempt)
  and stays recoverable via deterministic `requeue_stuck`.

Monkeypatches are restored before each real-method recovery assertion; stuck recovery uses a seeded old
lease (no wall-clock waiting).

## Validation summary (tested_code_sha = C6 = `3f4a9b2b`)
- `final-runs/gate-equivalent-c6-3f4a9b2b.txt` — 30-file de-duplicated gate-equivalent run, pipefail-correct:
  `502 passed, 1 warning in 410.83s` (0 failed / 0 errored; the warning is the FastAPI/Starlette
  deprecation), `PYTEST_EXIT=0`. (493 from the fourth round + 9 new C6 backstop tests.)
- `final-runs/ruff-c6.txt` — `RUFF_EXIT=0` (All checks passed) on the module + the test file.
- `final-runs/mypy-c6.txt` — `MYPY_EXIT=0` (Success) on the module.
- `final-runs/c6-no-code-drift.txt` — `git diff --exit-code C6 -- source_indexer.py test file` →
  `DRIFT_DIFF_EXIT=0` (worktree source/test match C6 exactly; no drift after testing).
- `final-runs/pre-e7-git-status.txt` — raw pre-E7 `git status --short`.

## Commit identity
Recorded in `12-corrective5-committed-tree-identity.md` (C6 SHA + parent, name-status, C6 patch + bundle
sha256; `tested_code_sha` / `evidence_parent_sha` / `evidence_scope`). E7's own SHA, its patch/bundle
checksums, the post-E7 `git status --short`, and the `C6..E7` proof live in the **detached manifest**
`final-runs/E7-detached-manifest.md` (post-commit — recording them inside E7 would be circular).
