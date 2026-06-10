# 241 — Phase 10 daily-brief deterministic-fallback run-state contract

Follow-up to [240](240-phase-10-daily-brief-usefulness-substrate.md). The usefulness substrate made
deterministic daily-brief candidates real and gated; this change fixes the run-STATE semantics so a
deterministic-useful brief with degraded local-model synthesis is reported and published as an
operator-usable fallback — distinct from an unusable run. Branch
`fix/daily-brief-deterministic-fallback-status` from `main@0db2993e`. Evidence:
`docs/evidence/daily-brief-deterministic-fallback-status/`.

## Result classes (`run_daily_local_agent`)

`status` (free TEXT; `ok = status != "failure"`) is finalized holistically AFTER the usefulness gate:

| Condition (apply mode) | status |
|---|---|
| render failed / egress blocked | `failure` |
| non-synthesis pipeline stage failed | `partial` |
| usefulness gate FAILED | `degraded` |
| usefulness PASSED + synthesis degraded + egress clean | `deterministic_success_synthesis_degraded` |
| usefulness PASSED + synthesis ok + egress clean | `success` |

Key change: the synthesis-degraded path no longer forces `partial`. `partial` (boolean) now equals
`status == "partial"` (the old `status=partial`/`partial=false` contradiction is gone). `synthesis`
degradation and `usefulness` are orthogonal signals reconciled at one finalization point.

## Operator-usability contract

- `operator_usable = usefulness_gate.passed and status != "failure"`.
- `synthesis_required_for_success = false`: a degraded model never blocks publishing a source-linked
  deterministic brief that passed the usefulness gate.
- Status JSON + payload carry `deterministic_fallback{used,reason,usefulness_gate_passed,published,
  stable_path,counts}`, `synthesis_status`, `operator_usable`, `deterministic_fallback_used`.

## Publishing (Option A)

`daily-brief-latest.html` is reserved for full synthesis success. The deterministic fallback publishes
`daily-brief-latest-deterministic.html` (always-written: dated + `-attempted`). The deterministic-latest
path updates on both full success and fallback. All stable writes are inside the fail-closed
`egress_clean` block; egress failure → `failure` and publishes neither stable path; a usefulness-gate
failure publishes neither and preserves `last-successful.json` (full-success only).

## Labeling

- Browser/Obsidian render an operator-usable banner ("Deterministic source-linked brief published…
  operator-usable because the usefulness gate passed") on a fallback, instead of the
  "Partial / NOT counted as successful" wording (reserved for genuine degraded/failure).
- When synthesis degrades, the `Model Enriched Intelligence` envelope is forced withheld
  (`available=false`, `degraded=true`, `withheld_reason=synthesis_degraded:<reason>`) and relabeled
  `Source-Linked Deterministic Brief` — never shown as available/healthy while synthesis is degraded;
  raw-free pending rows still surface under the deterministic label.

## Invariants preserved

No production DB mutation (validated on a `.backup` copy, sha256 unchanged); no external writeback /
cloud route / scheduler change; raw/egress guardrails intact; status/evidence remain hash/enum/count
only.
