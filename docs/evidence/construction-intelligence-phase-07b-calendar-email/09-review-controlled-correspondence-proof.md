# Phase 07B Prompt 09 — Review-Controlled Correspondence Intelligence: Proof (redacted)

Date: 2026-05-31 · Branch: `main` · Repo SHA at start: `999b819` · Package `1.3.0` ·
Schema head V23 (no migration — read-only feature).

Adds `CorrespondenceReviewBuilder` (new `construction/correspondence/` package) that
aggregates the redacted email/calendar read models into a project-level, advisory
correspondence preview + review warnings. **Read-only on every layer** — no Graph calls, no
token, no local SQLite writes. All values below are structural facts only — no UPN, tenant
GUID, paths, raw subjects, raw addresses, or body content.

## Files changed

- `src/hb_assistant/construction/correspondence/__init__.py` (new)
- `src/hb_assistant/construction/correspondence/correspondence_review.py` (new — builder +
  `CorrespondenceReviewReport` / `CorrespondenceWarning` / `CorrespondencePreview`)
- `src/hb_assistant/cli/graph.py` (`graph mail correspondence` read-only command + import)
- `tests/test_review_controlled_correspondence.py` (new — 4 tests)
- `docs/architecture/26-phase-07b-correspondence-review.md` (new)
- this evidence file

## Preflight (HEAD 999b819, all exit 0)

`git status --short` (clean except untracked `.claude/`), `python -m compileall -q src tests`,
`ruff check .` (All checks passed!), `mypy src` (Success), `pytest -m "not live and not
integration and not manual"` (0 failed).

## Post-implementation local validation (all exit 0)

| Command | Result |
| --- | --- |
| `python -m compileall -q src tests` | exit 0 |
| `ruff check .` | All checks passed! |
| `mypy src` | Success: no issues found in 163 source files |
| `pytest tests/test_review_controlled_correspondence.py -v` | 4 passed |
| `pytest -m "not live and not integration and not manual"` | 0 failed |
| `pytest tests/test_mutation_lockout.py` | passed (graph/ static no-write scan clean) |
| `hb-assistant construction-agent validate --json` | exit 0 |
| `hb-assistant procore validate --json` | exit 0 |
| `hb-assistant graph files status --json` | exit 0 |
| `hb-assistant graph mail status --json` | exit 0 |
| `hb-assistant graph calendar status --json` | exit 0 |
| `hb-assistant graph mail correspondence --json` (read-only) | exit 0 |
| `hb-assistant construction-agent data-quality gates --json` | exit 0 |
| `hb-assistant construction-agent data-quality no-writeback-proof --json` | proof_passed=true |

`ruff format` is NOT enforced repo-wide (222/341 files would reformat); `ruff check .` is the
authoritative lint gate and passes. `ruff format` was not run.

The 4 unit tests cover: thread + warning aggregation with high-sensitivity-first ordering and
the registry's "not a determination" framing; capped, redacted previews (thread_ref is a
16-char hash; no raw thread_key/subject/address); a no-writes assertion (table row counts
identical before/after `review()`); and lookback exclusion of old threads.

## Live read-only real-store proof (Graph-free, no writes)

`hb-assistant graph mail correspondence --project tropical --lookback-days 3650 --json`:

| Metric | Value |
| --- | --- |
| read_only / persisted | true / false |
| threads_total | 19 |
| threads_review_required | 2 |
| review_queue_open | 22 |
| classifications_total / review_required | 40 / 7 |
| meeting_email_candidates_total / review_required | 117 / 104 |
| previews returned | 10 (redacted; thread_ref hashed) |
| warnings | privileged_or_confidential_markers (high, 3); contracts (medium, 11); low_confidence_project_match (medium, 3); model_review (medium, 3); lien_releases (medium, 1); pay_applications (medium, 1) |

- **No writes:** read-only `sqlite3 COUNT(*)` over `email_thread_summaries`,
  `email_review_queue`, `email_model_classifications`, `meeting_email_relationship_candidates`
  was **identical before and after** the run (`19|22|40|117` both times).
- **Leak scan** over the emitted JSON: 0 raw emails (`@`), 0 URLs (`http`), 0 tenant-GUIDs.
- Sample preview (structural): `thread_ref` is a 16-char hash; `summary_redacted` =
  "thread: N message(s), M participant(s); window <ts> -> <ts>" (metadata only).
- `no-writeback-proof --json` after the run → `proof_passed=true`,
  `no_raw_values_persisted=true`.

## Scope notes

- No Microsoft 365 mutation/writeback; no SQLite writes; no Phase 07D meeting-prep readiness
  is claimed.
- Warnings are advisory signals, not determinations; sensitive/high-impact categories route
  to human review.
- The no-writeback prover does not yet scan the V11/V14/V23 email/calendar tables — deferred
  to Phase 07B Prompt 12.
