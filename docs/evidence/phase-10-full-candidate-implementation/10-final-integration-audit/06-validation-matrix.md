# Validation Matrix — Phase 10 Full Candidate Integration

Branch `experiment/phase-10-full-candidate-implementation` · baseline `0c75f4a7` · final HEAD `247b55d8`.

## Per-candidate (all green)

| # | Candidate | New tests | Targeted suite | ruff (changed) | mypy (changed) |
|---|---|---:|---|---|---|
| 01 | Daily Brief Convergence | 3 | 516 passed | clean | clean |
| 02 | Candidate Review UX | 3 | green (1 pre-existing) | clean | clean |
| 03 | Follow-up Watch Quality | 3 | 165 passed | clean | clean |
| 04 | Scheduler Reliability | 3 | green | clean | clean |
| 05 | Local Model Routing | 5 | 87 passed | clean | clean |
| 06 | Procore Expansion | 4 | 1115 passed (2 pre-existing) | clean | clean |
| 07 | Relationship / Entity | 4 | 287 passed | clean | clean |
| 08 | MCP Context Packet | 4 | 289 passed (1 pre-existing) | clean | clean |
| 09 | Document / File Parsing | 4 | 545 passed (1 pre-existing) | clean | clean |
| — | (integration fix) | — | mcp test 4 passed | — | — |

**33 new tests total** — all pass together (cross-candidate integration: no candidate broke another).

## Integration-wide

| Check | Command | Result |
|---|---|---|
| Compile (full) | `python -m compileall src tests` | ✅ OK |
| Cross-candidate suite | the 9 new test files together | ✅ 33 passed |
| Full suite | `pytest -q tests` | 31 failed — **all pre-existing** (see below) |
| Default-safe subset | `pytest -m "not integration and not live and not manual"` | 25 failed — **all pre-existing** |
| Safety scans | per-candidate forbidden-pattern scans | ✅ 9/9 PASS (0 findings) |
| Guard columns | candidates 01/03/07 | ✅ all zero |
| Production DB | sha256 before/after per candidate | ✅ unchanged (9/9) |

## Pre-existing failure proof (baseline worktree, `0c75f4a7`)

A disposable git worktree at the package baseline was used to run the failing test files. They fail
**identically at baseline** — confirming none are caused by this branch:

- `test_second_brain_no_writeback_proof` — flags a `.update()` in `daily_brief_intelligence.py`
  (unchanged from baseline; not touched by any candidate).
- `test_repo_sensitive_scan` — 2 unallowed findings at baseline (`test_local_model_eval.py:46`,
  `frontend/.../SourceConnectionsPanel.test.tsx:242`); both pre-existing files. The integration fix
  removed the only finding this branch had added, returning the scan to its baseline finding set.
- `test_launcher_scheduler::*`, `test_phase_08b_data_quality_gates::*`, `test_phase_08b_gate_coverage::*`,
  `test_phase_08c_financial_completeness`, `test_phase_09_embedding_policy`, `test_phase_09_review_burden_cli`,
  `test_retrieval` (embedder 768≠64 — model/env), `test_fastapi_analytics::*`,
  `test_email_body_indexing::*`, `test_email_body_security[graph.py]`, `test_calendar_event_indexing`,
  `test_automation_executor_service::*`, `test_phase_10_email_task_extraction` — all in subsystems no
  candidate touched; confirmed failing at baseline and/or by per-prompt stash-tests.

**Net new test failures introduced by this branch: 0.**
