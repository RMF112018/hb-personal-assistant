# Source Index Phase D — Scalability and Resilience

Status: normative acceptance specification
Scope: scratch-only metadata-index rehearsal; no production database, configured source root, NAS write,
deployment, watcher activation, or tenant operation

## Purpose

Phase D closes the scalability/resilience findings in the full-remediation audit with one reproducible,
machine-verifiable rehearsal. The default rehearsal creates a synthetic file tree and scratch SQLite
databases, then records raw outcomes and an explicit pass/fail evaluation.

## Acceptance criteria

| ID | Criterion | Terminal proof |
| --- | --- | --- |
| PD-AC-001 | Fresh 400,000- and 1,000,000-file generations complete through bounded resumable passes. | Both scale records are `completed`, use at least two passes, and expose every expected active row. |
| PD-AC-002 | Metadata bootstrap does not hash or parse file content, including large PDF/XLSX and corrupt ZIP/Office fixtures. | Hash and extraction tripwires remain at zero; content-indexed rows remain zero. |
| PD-AC-003 | The tree includes a 10,000-entry high-fanout directory, 32-level nesting, many small files, large PDF/XLSX files, and corrupt ZIP/DOCX/XLSX files. | Rehearsal configuration and exact file totals are recorded. |
| PD-AC-004 | Peak process RSS stays at or below 1,024 MiB and the 1M fresh scan sustains at least 500 files/second on the recorded host. | Machine evaluation checks both thresholds. |
| PD-AC-005 | A no-change generation performs zero metadata upserts and fast-skips all 1M files. | Exact generation counters. |
| PD-AC-006 | 0.1%, 1%, and 10% delta generations upsert exactly the touched count and fast-skip the remainder. | Exact generation counters per delta. |
| PD-AC-007 | Fresh-connection FTS search is at most 5,000 ms; warm p95 is at most 250 ms. | Timed path-only FTS query returning the known marker. |
| PD-AC-008 | Eight concurrent read-only clients complete without error; p95 is at most 1,000 ms. | Per-query timing and failure count. |
| PD-AC-009 | A populated WAL checkpoints without contention, truncates to at most 4,096 bytes, passes integrity checking, and supports a subsequent write/read cycle. | Positive pre-checkpoint bytes and frame counts, checkpoint tuples, integrity result, recovery result, and final byte count. |
| PD-AC-010 | Write-lock contention returns a bounded lock error within 10 seconds and the next generation completes. | Timed contention result and recovery generation. |
| PD-AC-011 | EIO, ESTALE, and permission failures suspend without reconciliation; over-limit fanout fails without reconciliation. | CI fault-injection tests. |
| PD-AC-012 | A real killed scanner resumes the same durable generation from a committed cursor and completes without a permanent pin. | CI process-kill/resume test. |
| PD-AC-013 | The evaluator fails closed when any required SLO/invariant fails. | Negative evaluator test. |

The “cold” search measure means a fresh SQLite connection/page cache. It does not claim a dropped operating
system page cache or live-NAS cold-cache measurement. The synthetic host result is the Phase D engineering
gate; deployment attestation and live activation remain separate later phases.

## Reproduction

```bash
PYTHONPATH=src .venv/bin/python scripts/source_index_phase_d_rehearsal.py \
  --targets 400000,1000000 \
  --expected-head "$(git rev-parse HEAD)" \
  --json-out /absolute/evidence/SOURCE-INDEX-PHASE-D-PR329-EXACT-HEAD-EVIDENCE-20260728.json \
  --manifest-out /absolute/evidence/SOURCE-INDEX-PHASE-D-PR329-EXACT-HEAD-MANIFEST-20260728.json
```

The exact-head evidence form fails before scanning unless the supplied head matches a
clean worktree. Its manifest binds the repository remote, branch, head and tree,
base, command, script hash, dependency/lock identities, installed package inventory,
Python/SQLite identity and compile options, material configuration, SLOs, filesystem
identity, result hash and byte count, evaluator result, timestamps, and process exit
status.

Run the CI-safe fault and reduced-scale gate with:

```bash
bash scripts/ci_source_index_phase_d_gate.sh
```

The command returns non-zero if any machine-evaluated criterion fails. Scratch content is removed by default.
