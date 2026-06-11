# Final Handoff — Phase 10 Email Follow-Up Candidate Projection

## Branch / Commit
- Branch: `feature/phase-10-email-followup-candidate-projection`
- Base: `e7c1b51` (= main = origin/main; PR 23 + PR 22 merged)
- Main untouched by this agent: yes
- Commit SHA: see commit (created at handoff)
- PR opened: no (commit only, per request)

## Summary
- Implemented: deterministic, metadata-only, raw-safe email follow-up candidate projection
  (`email_followup_candidate_projection.py`) over the V49 structured email/thread substrate; new
  `email_followup_projection` pipeline stage (after `email_calendar_projection`); usefulness-gate +
  stage-context extensions; commitment-test fixture fix + regressions.
- Intentionally not implemented: raw-body (`load_body`) extraction — deferred to a future audited pass.
- Schema changed: no (existing idempotent tables suffice).
- Production DB touched: no (read-only copy; sha256 identical pre/post).

## Changed Files (mine)
```text
src/hb_assistant/construction/second_brain/local_ai/email_followup_candidate_projection.py   (new)
src/hb_assistant/construction/second_brain/local_ai/pipeline.py                              (mod)
src/hb_assistant/construction/second_brain/local_ai/daily_run.py                            (mod)
src/hb_assistant/construction/second_brain/local_ai/usefulness_gate.py                      (mod)
tests/test_phase_10_email_followup_candidate_projection.py                                   (new)
tests/test_phase_10_email_task_extraction.py                                                (mod)
tests/test_phase_10_usefulness_gate.py                                                      (mod)
docs/architecture/phase-10-email-followup-candidate-projection.md                            (new)
docs/evidence/phase-10-email-followup-candidate-projection/*                                 (new)
```

## Tests Run
| Test / Command | Result | Evidence |
|---|---|---|
| Repo guard | on feature branch, clean (mine) | 00 |
| New extractor/persistence/integration suite (13) | pass | 03,04,06 |
| Commitment regression + 2 new (14 in file) | pass | 08 |
| Usefulness gate (11 incl 4 new) | pass | 07 |
| Targeted sweep (125 tests) | pass | 10 |
| No-raw-leak scan | unsafe_finding_count = 0 | 09 |
| ruff (changed files) | clean | — |

## DB Copy Validation
- Audit root: `/tmp/hb-phase10-email-followup-candidate-projection-20260611-132651`
- Copied from plain app-support prod DB, read-only; integrity ok; schema V49.
- Apply only on `/tmp` copy. Prod sha256 identical pre/post -> untouched.
- Owner-unknown: 1 candidate, coverage 1.0, idempotent. Owner-configured: 4 candidates
  (time_sensitive), coverage 1.0, idempotent, data-gap -> populated.

## Candidate Counts (owner-configured, real-data copy)
| Family | Generated | Persisted | Daily-Brief |
|---|---:|---:|---:|
| time_sensitive_followup | 4 | 4 | 4 (follow_up) |
| (others) | 0 | 0 | 0 |

## Source-Ref Coverage
- Email-derived daily-brief candidates: 4 · with refs: 4 · coverage: 1.0 (threshold 100%) · uncovered: none.

## Project-Key Coverage
- resolved 2 · review_required 2 · not_project_related 0 · coverage 0.5 · invented keys: no.

## Guard / Leak Results
- Guard columns zero: yes (all 4 tables). No raw body/HTML/recipient arrays/URLs/tokens/model
  prompts/responses. No-raw-leak scan: 0 findings.

## Usefulness Gate
- Verdict: useful when source-linked candidates exist; degrades on stage failure, project gap without
  review, missing refs (executive coverage), and empty-followup-with-rows-no-data-gap. Data-gap card
  preserved when no candidates; replaced when candidates exist.

## Known Failures / Quarantines
- None. Pre-existing commitment test fixed (deterministic fixture incoherence; rule unchanged).

## Production Safety Statement
No production DB rows were mutated. No external systems were mutated. No
email/calendar/Graph/Procore/SharePoint/OneDrive/Obsidian writeback ran. All apply validation ran only
on `/tmp` copies; the slice never opened prod for write (prod sha256 identical pre/post).

## Merge Readiness
- Merge-ready: yes. Required before merge: none. Recommended after merge: configure
  `HB_ASSISTANT_OWNER_ADDRESSES`/`_DOMAINS` to activate direction-dependent families on real data;
  consider a future audited body-extraction pass for body-only commitments/asks.
