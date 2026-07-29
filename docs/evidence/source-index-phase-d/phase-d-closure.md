# Source Index Phase D Closure

Disposition: **CORRECTIVE — exact-head rerun and fresh review required**

## Repository identity

- Repository: `/Users/bobbyfetting/hb-personal-assistant`
- Branch: `bf/source-index-phase-d-scale-resilience`
- Base branch: `origin/main`
- Base SHA: `bd3c96442346150f5fc86fa20a40f5ddaf9129f2`
- Initial reviewed head: `8e50ab74b39c62498676a501d426d443634f94f2`
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
| PD-AC-001 | RERUN REQUIRED | Initial values preserved; exact-head provenance required |
| PD-AC-002 | RERUN REQUIRED | Initial tripwire values preserved; exact-head provenance required |
| PD-AC-003 | RERUN REQUIRED | Topology remains deterministic; exact-head manifest required |
| PD-AC-004 | RERUN REQUIRED | Initial performance preserved; exact-head environment binding required |
| PD-AC-005 | RERUN REQUIRED | Initial no-change result preserved; exact-head provenance required |
| PD-AC-006 | RERUN REQUIRED | Initial delta counts preserved; exact-head provenance required |
| PD-AC-007 | RERUN REQUIRED | Initial search result preserved; exact-head provenance required |
| PD-AC-008 | RERUN REQUIRED | Initial concurrency result preserved; exact-head provenance required |
| PD-AC-009 | CORRECTED, RERUN REQUIRED | Evaluator now requires populated WAL bytes/frames, successful truncation, integrity, and post-checkpoint write/read recovery |
| PD-AC-010 | RERUN REQUIRED | Initial lock result preserved; exact-head provenance required |
| PD-AC-011 | PASS | EIO, ESTALE, EACCES, and fanout tests preserve reconciliation safety |
| PD-AC-012 | PASS | Real killed process resumes the same committed generation and completes |
| PD-AC-013 | PASS | Negative evaluator test proves SLO failures cannot report PASS |

The initial machine evaluation in
`docs/evidence/source-index-phase-d/phase-d-400k-1m-rehearsal.json` is preserved
with SHA-256
`2c045b5c6b881de0b46f992856fcf355ba6e79145f311ffebb76236d71759288`,
but it is superseded for terminal closure by independent findings `PD329-F-001`
and `PD329-F-002`.

The corrective head must be run without further repository changes and publish:

- `SOURCE-INDEX-PHASE-D-PR329-EXACT-HEAD-EVIDENCE-20260728.json`
- `SOURCE-INDEX-PHASE-D-PR329-EXACT-HEAD-MANIFEST-20260728.json`

The manifest and evidence must pass byte-exact Drive readback before fresh
independent review.

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

## Independent review corrective cycle

The exact-head review
`REVIEW-SOURCE-INDEX-PHASE-D-PR329-20260728.md` (Drive ID
`1no-lEdOM6_wrOZRfoyXAVYilaOA9zMv8`, SHA-256
`b75c76ab9bf428b2b8ffd6fa21a7cf740f638bc77269936aeec2a48acfb0ad19`)
accepted the production SQL and resilience tests and opened two blocking
findings:

- `PD329-F-001`: bind the terminal rehearsal to the exact candidate,
  command, script, dependencies, configuration, environment, result bytes,
  and exit status.
- `PD329-F-002`: checkpoint a deterministically populated WAL and prove
  truncation, integrity, and subsequent read/write recovery.

This corrective cycle is bounded to those findings plus the observed scratch
cleanup reporting defect.

## Deviations and residual risk

No acceptance criterion was weakened. The only command-level deviation was invoking
the exact legacy Ruff target list through the working interpreter because its generated
launcher was stale.

The scale evidence is synthetic and local. “Cold” means a fresh SQLite connection, not
an operating-system cache drop or live-NAS measurement. Live deployment, NAS
attestation, and production activation remain outside Phase D.

Recommended next gate: exact-head rehearsal publication followed by fresh
independent review. This recommendation does not authorize merge.
