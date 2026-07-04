# 07 — Duplicate-Prevention Proof — RUNBOOK (PENDING LIVE EXECUTION WITH BOBBY)

Status: **HOLD** — live NAS, per-step approval required. Not executed this session.
(Mechanisms already proven against temp DBs in `03`; this is the live-NAS confirmation.)

## Four proofs
1. **Second-watcher ownership** — start a 2nd watcher against the same NAS DB → must degrade
   `watcher_not_owner` (fail-closed, does not clear the live lease; owner host attributed).
   *Temp-DB proof: `test_second_watcher_runs_degraded` (passing).*
2. **Duplicate card generation** — re-run card generation for the same source → no 2nd card
   (dedup on `UNIQUE(source_id, note_rel_path)`).
3. **Expected-SHA overwrite** — `patch_note` with a stale expected SHA → refused.
4. **Cross-root non-collision (post-V99)** — same rel_path under `nas_test` vs a 2nd root → **distinct**
   `source_id`s and **distinct** cards (live confirmation of the 3c fix + live-DB V99 backfill delta).
   *Temp-DB proof: `test_distinct_roots_same_relpath_coexist`, migration round-trip (passing).*

## Acceptance
- All four hold on the live NAS DB; row-count deltas captured; **or** a blocker is declared before cutover.
