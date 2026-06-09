# Relationship Candidate Engine — Live Proof (Follow-On)

Redacted, command-output-focused evidence for the Phase 10 follow-on relationship candidate engine.
Architecture: [233](../../architecture/233-phase-10-relationship-candidate-engine.md). All live
proof ran against a **DB copy** under `/tmp` — the production/Dev DB was never mutated. No raw
subjects, bodies, addresses, URLs, join links, payloads, prompts, responses, or tokens appear here.

## Branch / git state

```
branch : experiment/local-agent-family-proof
main   : 63ba1b9f61322489f643d6237ad0f12b0ab0141e   (unmodified)
commits (this package):
  117aa8e  Add Phase 10 relationship candidate core
  0e81c66  Add relationship candidate CLI surface
  a3f6197  Surface relationship context in daily brief
  <docs>   Document Phase 10 relationship candidate engine
```

## Schema readiness (DB copy)

```
schema_version = 43
email_thread_raw_context        = 1148 rows
calendar_event_raw_content      =  500 rows
phase10_relationship_candidates =    0 rows  (before proof)
```

Table `phase10_relationship_candidates` exists at V41; no migration required. The 13 Phase 10 guard
columns are present with `CHECK(col = 0)`.

## Dry-run zero-write proof

```
$ hb-assistant second-brain relationship-candidates scan --db <copy> --as-of 2026-06-09T05:00:00+00:00 \
    --limit 25 --scan-threads 50 --scan-events 50 --dry-run --json
  summary: scanned_relationships=0 candidates=0 would_persist=0 persisted=0   (default 50×50 window)
$ ... --limit 50 --scan-threads 500 --scan-events 500 --dry-run --json
  summary: scanned_relationships=50 candidates=50 would_persist=50 persisted=0  by_class={moderate:50}
$ sqlite3 <copy> "SELECT COUNT(*) FROM phase10_relationship_candidates;"
  0
```

Dry-run persists nothing regardless of window size.

## Apply (capped) proof

```
$ ... --limit 50 --scan-threads 500 --scan-events 500 --apply --max-persist 5 --json
  summary: would_persist=50 persisted=5 skipped_existing=0 skipped_capped=45 skipped_missing_ref=0
  rows after = 5   (persisted ≤ cap; remainder reported as skipped_capped)
```

## Idempotency proof (canonical, fresh copy)

```
$ ... --apply --max-persist 50 --json          # cap covers all 50 candidates
  summary: persisted=50 skipped_existing=0      rows = 50
$ ... --apply --max-persist 50 --json           # identical re-run
  summary: persisted=0  skipped_existing=50      rows = 50  (unchanged)
$ sqlite3 <copy> "SELECT COUNT(DISTINCT relationship_candidate_id) ...;"  -> 50  (== row count, no dupes)
```

Re-running the identical command persists nothing; distinct ids equal the row count (no duplicates).
With a cap smaller than the candidate set, repeats are intentionally append-only (next batch
persisted, prior batch reported `skipped_existing`) — never duplicated.

## Guard-column proof

```
$ sqlite3 <copy> "SELECT SUM(raw_email_body_persisted + raw_document_text_persisted +
    raw_calendar_payload_persisted + raw_procore_payload_persisted + raw_prompt_persisted +
    raw_response_persisted + signed_url_persisted + download_url_persisted +
    external_writeback_performed + graph_writeback_performed + procore_writeback_performed +
    email_send_performed + calendar_mutation_performed) FROM phase10_relationship_candidates;"
  0
```

All 13 guard columns sum to 0 across every persisted relationship row.

## Source-table immutability

```
before: email_thread_raw_context=1148  calendar_event_raw_content=500
after  : email_thread_raw_context=1148  calendar_event_raw_content=500   (unchanged)
```

## Fail-closed proof

```
$ ... --apply --json            # no --max-persist
  exit_code = 2   ok=false   error=apply_requires_max_persist   rows unchanged
$ ... --min-confidence 1.5      # out of range
  exit_code = 2   error=min_confidence_out_of_range
```

## Redaction / egress scan

Scanned the `--summary` CLI JSON, the persisted row columns, and the rendered brief (JSON +
markdown) for `@`, `http`, `://`, `<`, `>`, `join`, `teams.microsoft`, `zoom.us`, `webex`, `BEGIN`:

```
CLI --summary JSON ............ NO forbidden tokens   (ref fields are 16-hex hashes; reason codes [a-z_0-9]+)
persisted rows ................ NO forbidden tokens
brief relationships+markdown .. NO forbidden tokens
sample reason_redacted ........ "subject_similarity,explicit_meeting_reference,participant_overlap"
```

## Daily-brief enrichment proof

```
$ hb-assistant second-brain daily-brief render --db <copy> --date 2026-06-09 --limit 50 --markdown --json
  ok=true  summary.relationships=10  relationships[]=10  "Related Context" section present  forbidden tokens: NONE
  phase10_relationship_candidates row count unchanged by render (50) → render is read-only
```

The relationship section is bounded (default `relationship_limit=10`) and appears only because rows
exist; on a DB with zero relationship rows the brief is byte-identical to before this work.

## Daily-pipeline regression proof

```
$ hb-assistant second-brain pipeline run --db <copy> --as-of 2026-06-09T05:00:00+00:00 --dry-run --json
  ok=true  stages = [follow_up_watch, procore_digest, calendar_prep, daily_brief_synthesis, daily_brief_render]
           (relationship_candidates ABSENT — default run unchanged)
$ ... --dry-run --include-relationship-candidates --json
  ok=true  stages = [..., daily_brief_synthesis, relationship_candidates, daily_brief_render]  total_persisted=0
           (opt-in stage runs immediately before render; dry-run persists nothing)
```

## Tests / lint / types

```
package test set (10 files) ........ 156 passed
new test_phase_10_relationship_candidates.py .. 30 passed (core + CLI + pipeline + brief)
ruff check (local_ai + changed files) ......... All checks passed
mypy src/.../local_ai ......................... Success (32 files)
ruff format --check (changed scope) ........... new module + test + pipeline + render clean
```

### Pre-existing / unrelated failures (NOT introduced by this package)

- `test_phase_10_email_task_extraction.py::test_commitment_persists_to_commitment_table` — fails
  identically at base commit `581f0ee6` (verified in a throwaway worktree). Branch-independent.
- `ruff format --check` reports drift in pre-existing files this package did not modify (e.g.
  `relationship_scoring.py`, `structured_output.py`); the giant CLI/store files carry pre-existing
  repo-wide style drift and are outside the package's stated format scope (`local_ai` + `tests`).
  Reformatting them was declined to keep the diff surgical.

## Rollback

Revert the three additive commits in reverse order (brief → CLI/pipeline → core). No schema change to
undo. If a DB-copy apply produced wrong rows, discard the copy and fix code before re-applying.
