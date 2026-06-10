# Final Handoff Template

## Summary

Repaired the second-brain daily-brief pipeline so a technically successful run cannot produce an
operator-useless brief. The fix is a deterministic read-model + gate substrate *before* model work:
calendar category resolution, Procore signal ranking + aggregate suppression, a single source-linked
candidate-projection writer, a model-facing source-ref gate, and a daily-run usefulness gate. No
schema migration (V45 reuse). Production DB never mutated.

## Branch / HEAD

`fix/daily-brief-usefulness-repair` — see `git rev-parse HEAD` at handoff (tip is the handoff commit).

## Base Relationship

Branched from `main @ dbff6e89` (schema V45). `main` already contained all Phase 10 `local_ai` code +
the alias resolver; the prior experiment branch was an ancestor of `main`.

## Commit List

```
docs(second-brain): add daily brief usefulness repair baseline
fix(second-brain): resolve calendar project aliases for brief candidates
fix(second-brain): rank Procore signals for daily brief usefulness
fix(second-brain): project source-linked daily brief candidates
fix(second-brain): gate model synthesis on source-linked useful context
fix(second-brain): enforce daily-run usefulness status gates
test(second-brain): prove daily brief usefulness repair on DB copy
docs(second-brain): add daily brief usefulness substrate architecture + handoff
```

## Files Changed

New modules: `calendar_category.py`, `procore_ranking.py`, `daily_brief_candidate_writer.py`,
`source_ref_gate.py`, `usefulness_gate.py` (under `construction/second_brain/local_ai/`).
Modified: `calendar_prep.py`, `procore_digest.py`, `daily_brief_context_packet.py`,
`daily_brief_llm_synthesis.py`, `daily_run.py`, `project_aliases.py`, `store/repositories.py`.
New tests: `test_phase_10_calendar_category.py`, `test_phase_10_procore_ranking.py`,
`test_phase_10_daily_brief_candidate_projection.py`, `test_phase_10_daily_brief_source_ref_gate.py`,
`test_phase_10_usefulness_gate.py`; updated `test_phase_10_calendar_meeting_prep.py`.
Docs: `docs/architecture/240-phase-10-daily-brief-usefulness-substrate.md`; evidence under
`docs/evidence/daily-brief-usefulness-repair/`.

## Priority 1 — Calendar Project Alias Resolution

`calendar_category.py` adds the project / internal_company / internal_training / internal_time_off /
needs_review / unknown category. The project arm delegates to `resolve_project_alias` (added to
`project_aliases.py`; `resolve_project` now wraps it) — no forked alias logic. `calendar_prep`
resolves from the **real raw subject** (the persisted `subject_redacted` is a hash placeholder),
persisting real project keys or review-safe sentinels. DB-copy proof: calendar resolution 0.0 → 1.0.

## Priority 2 — Procore Signal Ranking and Suppression

`procore_ranking.py` promotes due-soon / overdue / recent / source-change-linked / financial /
high-critical signals and suppresses stale aggregates + semantically-closed (`observation_closed`)
signals. `procore_digest` persists only ranked promoted executive rows; aggregate backlog → a
`suppressed_backlog` diagnostic. DB-copy proof: 10 ranked executive rows, 0 aggregate sludge selected.

## Priority 3 — Daily-Brief Candidate Projection

`daily_brief_candidate_writer.persist_candidate_with_refs` is the single persistence contract (id
derivation, hash-only `candidate_source_refs`, idempotency). Calendar + Procore both route through it.
DB-copy proof: 18 candidates persisted (was 0), 18/18 source-linked.

## Priority 4 — Source-Ref Gate and Model-Facing Contract

`source_ref_gate.py` feeds the model only source-linked candidates, reports coverage, and withholds
synthesis when all rows are unlinked (`synthesize_daily_brief` → `status=blocked`,
`no_source_linked_context`). Executive rows require 100% coverage for `success`.

## Priority 5 — Usefulness / Success Gates

`usefulness_gate.py` + integration in `run_daily_local_agent`: an apply-mode `success` that fails the
usefulness bar is downgraded to `partial`, preserving the last-successful brief and not overwriting
`daily-brief-latest.html`. Status JSON carries a `usefulness_gate` block.

## Schema Decision

**Reuse V45 — no migration.** Internal categories encoded as `__…__` `project_key` sentinels;
why-today → `reason_redacted`; rank → `priority`; quality → `confidence`; source links via the
existing `candidate_source_refs` table.

## Test Results

- `compileall src tests` — OK.
- Targeted suite `test_phase_10_daily_run* / daily_brief* / procore* / calendar*` — **208 passed**.
- New focused tests: calendar category (11), procore ranking (12), candidate projection (6),
  source-ref gate (8), usefulness gate (7) — all pass.
- `ruff check` on changed files — clean. `mypy` on 12 changed source files — clean.
- Pre-existing unrelated failures: none introduced; scope not broadened.

## DB-Copy Live Proof

On a `.backup` copy of the V45 audit DB (`--apply --raw --write-obsidian`, outputs under `/tmp`):
candidates 0→18 (calendar 8 / procore 10), source-ref coverage 0.0→1.0, calendar resolution 0.0→1.0
(5 project-resolved + 3 internal, none `__unassigned__`), Procore aggregate sludge selected 0, guard
columns 0. Usefulness gate `verdict=useful`. Status `partial` only because local-model synthesis
fail-closed on empty output (`empty_synthesis_low_quality`) — deterministic fallback preserved, not a
false success. Details: `../06-db-copy-live-proof/DB_COPY_PROOF.md`. Raw `/tmp` artifacts (path only):
`/tmp/daily-brief-usefulness-repair-20260610-055102/{html,vault,status,daily-run-copy-apply.json}`.

## Production DB Unchanged Proof

sha256 identical before/after:
`f93b78081dfbbd7d40ebbfc9254227eab7d306bb08d73e8b92d76e7b33ae4759`
(`../06-db-copy-live-proof/prod-before.sha256` / `prod-after.sha256`).

## Safety / Forbidden Scan

Forbidden-string scan over `docs/evidence/daily-brief-usefulness-repair` — **clean**. Guard columns
zero on persisted candidates. No external writeback / send / draft / calendar / Procore / Graph
mutation; no cloud model route; raw subjects used for resolution only, never persisted/emitted;
outputs confined to `/tmp`.

## Before / After Brief Quality Summary

Before: success reported; empty deterministic sections; calendar all `__unassigned__`; Procore brief
dominated by giant aggregate counts; no source-linked candidate layer. After: 18 source-linked
candidates with real project keys / internal categories, 10 ranked Procore rows (aggregates demoted
to a labeled suppressed-backlog diagnostic), 100% executive source-ref coverage, and an honest status
(`useful` gate; `partial` when the model degrades, preserving the last good brief).

## Known Limitations

- Local-model synthesis returned empty/low-quality on this DB copy (`empty_synthesis_low_quality`),
  so the run is `partial`; the deterministic substrate is fully useful. Improving the synthesis
  prompt/profile is out of scope (the package forbids model replacement / prompt-only fixes).
- 44 of 161 calendar index rows have no `calendar_event_raw_content`; those resolve from the
  (hashed) redacted subject only and fall to review-safe `needs_review`/`unknown`.
- `EXECUTIVE_SECTIONS` and ranking weights are deterministic constants, not yet policy-configurable.

## Stop Conditions

None triggered. Production DB unchanged; no writeback; no cloud route; no raw leakage; guard columns
zero; no false success; executive source-ref coverage 100%; calendar project-like items resolved;
Procore executive rows ranked (no sludge); no new test failures; branch isolated to intended files.

## Manual Verification Commands

```bash
cd /Users/bobbyfetting/hb-personal-assistant && source .venv/bin/activate
python -m compileall src tests
pytest -q tests/test_phase_10_daily_run*.py tests/test_phase_10_daily_brief*.py \
          tests/test_phase_10_procore*.py tests/test_phase_10_calendar*.py
# DB-copy proof (production stays read-only):
TS="$(date +%Y%m%d-%H%M%S)"; PROD_DB="$HOME/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"
ROOT="/tmp/dbur-$TS"; DB="$ROOT/copy.sqlite"; mkdir -p "$ROOT/vault" "$ROOT/html" "$ROOT/status"
sqlite3 "$PROD_DB" ".backup '$DB'"; shasum -a 256 "$PROD_DB"
.venv/bin/hb-assistant second-brain daily-run run --apply --raw --write-obsidian --confirm-vault-write \
  --as-of 2026-06-10T05:00:00-04:00 --vault-brief-dir "$ROOT/vault" --browser-output-dir "$ROOT/html" \
  --status-dir "$ROOT/status" --db "$DB" --json | python -m json.tool | grep -A20 usefulness_gate
shasum -a 256 "$PROD_DB"   # must be identical
```

## Merge Recommendation

**Recommend merge.** All five priorities implemented and validated; V45 reuse (no migration);
targeted suite + changed-file lint/type green; DB-copy proof shows the audit's findings repaired with
the production DB unmutated and no false success. Follow-up (separate scope): improve local-model
synthesis quality so the repaired substrate yields a full `success` brief end-to-end.
