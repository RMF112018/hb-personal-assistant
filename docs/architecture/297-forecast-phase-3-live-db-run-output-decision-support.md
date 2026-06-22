# ADR 297 — Forecast Phase 3: gated live-DB run-output + decision-support projection

## Status

Accepted.

## Context

All forecast DB layers (schema + read-only projectors) are on main, but projection only ever
landed in temp DBs — the live DB had V59 populated (Phase 14) yet `forecast_runs` (V58) and the
V63/V66 families were empty, so the persistence layer was inert. This phase performs the gated
cutover for the forecast run graph, under the proven Phase-14 discipline.

Verified live state (schema v67): V59 tropical = 127/6324/1081; `forecast_runs` and all V63/V66
tables = 0 tropical. V63/V66 FK `forecast_runs`, and the V66 engine derives maturity/availability
from live V59 and reads per-code confidence from V63 — so the write order is
`forecast_runs` anchor → V63 → V66.

## Decision

New CFR-side workflow `workflows/live_db_run_output_projection.py`
(`run_controlled_live_db_run_output_projection`) generalizing Phase 14 to the run graph, reusing
its scaffold verbatim (`live_db_certification._ro_conn/_digests/_raw_strings/_rowcount/
_file_provenance/_write_json_deterministic`; `live_db_source_domain_projection._columns/
_tropical_count/_schema_version/_sha256_file/_verify_inserted/_is_under/_LIVE_ROOT`). hb_assistant
projectors are lazy-imported and only run against NON-LIVE temp DBs.

Gated sequence (rc 0/1/3, identical posture to Phase 14):
1. Preflight (allow-gate, tropical-only, explicit analysis/source packages, work_root not under
   `_LIVE_ROOT`, run_id, live-DB identity).
2. Read-only pre-write audit: schema ≥ 66, run-graph tables present, **live V59 populated**
   (V66 needs it), existing-tropical gate.
3. Fresh non-live temp chain: migrate → `project_source_domain` (V59) → insert `forecast_runs`
   anchor → `project_run_output` (V63, all downstream packages) → `project_decision_support`
   (V66, reads temp V59 + V63). Capture rows + `raw_json` digests.
4. **V59 consistency gate**: temp V59 counts must equal live V59 counts (source-drift guard, so
   the temp-derived V66 matches live).
5. Expected-counts gate (optional) — before backup.
6. WAL-checkpoint-guarded byte backup (`…before-phase3-run-output.sqlite`); fail-closed on nonzero WAL.
7. One `BEGIN IMMEDIATE` txn (`PRAGMA defer_foreign_keys=ON`): per target table, column-match →
   `DELETE … project_key='tropical'` → INSERT temp rows → in-txn count verify. Non-tropical rows
   preserved. Rollback on any exception. (Operator/required-assumptions tables stay empty.)
8. Post-write certification: re-project a FRESH temp and compare live `raw_json` digests per
   V63/V66 table (forecast_runs has no raw_json → verified by anchor presence). `certified_match`
   ⇒ rc 0; mismatch ⇒ rc 1 (backup recorded).

V59 is read, never written here. New CLI `live-db-run-output-project` mirrors
`live-db-source-domain-project` (rc 0/1/3).

## Consequences

- The forecast run graph (anchor + V63 + V66) can now be populated on the live DB, reversibly and
  certified — unblocking read-model API/UI surfacing.
- **No schema/migration/count change** ⇒ merges cleanly through the concurrent schedule churn.
- The real `--allow-live-db-write` execution remains a separate, explicitly-authorized operator
  step; nothing here runs it. All tests target a synthetic temp "live" DB.
- Relaxed one pre-existing stale assert in the Phase-14 test (`schema_version == 61` → `>= 59`)
  that the schedule version bumps (now V67) had left red.

## Verification

`tests/test_forecast_live_db_run_output_projection.py`: happy-path certified (anchor + V63 + V66
written, V59 untouched, all digest tables match), and gates — no-allow → rc3; live V59 empty →
rc3; nonzero WAL → rc3 (no backup); expected-count mismatch → rc3 (no write); existing-tropical
refuse/replace; non-tropical preservation; idempotent; CLI rc0/rc3. Phase-14 test still green;
ruff clean on the new workflow and `cli.py` lint.
