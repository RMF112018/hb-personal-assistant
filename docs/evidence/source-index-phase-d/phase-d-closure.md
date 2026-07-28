# Source Index Phase D Closure

Disposition: **PASS — ready for pull-request review**

## Repository identity

- Repository: `/Users/bobbyfetting/hb-personal-assistant`
- Branch: `bf/source-index-phase-d-scale-resilience`
- Base branch: `origin/main`
- Base SHA: `bd3c96442346150f5fc86fa20a40f5ddaf9129f2`
- Work item: source-index Phase D scalability and resilience remediation
- Execution scope: scratch-only local rehearsal and CI-safe fault injection; no live NAS,
  production database, deployment, watcher activation, or tenant operation

## Implementation

- Added a deterministic 400,000/1,000,000-file rehearsal with high fanout, deep nesting,
  large and corrupt format fixtures, no-change/delta generations, FTS timing, concurrent
  readers, WAL checkpointing, and lock recovery.
- Added reduced-scale CI coverage for the rehearsal, EIO/ESTALE/permission faults,
  fanout failure, real process kill/resume, lock contention, and fail-closed evaluation.
- Restored scalable SQLite access paths by adding the live-locator predicate required by
  partial indexes and enforcing a selective FTS-first join order.
- Added the Phase D gate to the source-index GitHub workflow.

## Acceptance matrix

| Criterion | Result | Evidence |
| --- | --- | --- |
| PD-AC-001 | PASS | 400k completed in 17 passes; 1M completed in 41 passes; exact active counts |
| PD-AC-002 | PASS | Zero hash/extract invocations and zero content rows |
| PD-AC-003 | PASS | 10k fanout, 32-level depth, small, large, and corrupt fixtures recorded |
| PD-AC-004 | PASS | Peak RSS 386.9 MiB; 1M fresh throughput 3,259.2 files/s |
| PD-AC-005 | PASS | No-change: zero upserts and 1,000,000 unchanged |
| PD-AC-006 | PASS | Exact 1,000 / 10,000 / 100,000 upserts for 0.1% / 1% / 10% deltas |
| PD-AC-007 | PASS | Fresh-connection FTS 12.558 ms; warm p95 11.116 ms |
| PD-AC-008 | PASS | 8 readers, 160 queries, zero failures, p95 246.674 ms |
| PD-AC-009 | PASS | Checkpoint not busy; WAL truncated to zero bytes |
| PD-AC-010 | PASS | Lock error in 5.212 s; recovery completed with 1M active rows |
| PD-AC-011 | PASS | EIO, ESTALE, EACCES, and fanout tests preserve reconciliation safety |
| PD-AC-012 | PASS | Real killed process resumes the same committed generation and completes |
| PD-AC-013 | PASS | Negative evaluator test proves SLO failures cannot report PASS |

The machine evaluation in
`docs/evidence/source-index-phase-d/phase-d-400k-1m-rehearsal.json` passed every
required check. Its SHA-256 is
`2c045b5c6b881de0b46f992856fcf355ba6e79145f311ffebb76236d71759288`.

## Validation

- `scripts/ci_source_index_phase_d_gate.sh`: PASS — 38 tests and Ruff.
- `scripts/ci_source_index_phase_c_gate.sh`: PASS — Phase C tests, Ruff, and strict
  mypy.
- Full `tests/test_source_index_repository.py`: PASS.
- `mypy src/hb_assistant/obsidian_mcp/source_index_repository.py`: PASS.
- The legacy `scripts/ci_source_index_gate.sh` pytest body passed. Its final bare
  `ruff` launcher was unavailable because the local virtual-environment entry-point
  shebang references a removed Python 3.12 interpreter; the exact Ruff target list was
  rerun through the working virtual-environment Python 3.14 interpreter and passed.
- `git diff --check`: PASS.

## Preserved failed evidence

- `failed-run-001.md`: partial-index predicate defect caused an unbounded per-file
  locator scan.
- `failed-run-002.md`: no-change batch reads and observation stamps missed the same
  live-locator predicate.
- `failed-run-003.md`: SQLite selected a root-locator-first FTS plan; the remediation
  enforces the selective FTS-first loop order.

## Deviations and residual risk

No acceptance criterion was weakened. The only command-level deviation was invoking
the exact legacy Ruff target list through the working interpreter because its generated
launcher was stale.

The scale evidence is synthetic and local. “Cold” means a fresh SQLite connection, not
an operating-system cache drop or live-NAS measurement. Live deployment, NAS
attestation, and production activation remain outside Phase D.

Recommended next gate: pull-request review and hosted CI. This recommendation does not
authorize merge.
