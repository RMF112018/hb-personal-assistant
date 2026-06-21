# ADR 282 — Forecast UI: live-data generation validation for all four DB-config-backed generators

- **Status:** Accepted
- **Date:** 2026-06-21
- **Phase:** Forecast CLI→UI product, DB-config-backed generation (live-data validation)
- **Builds on:** ADR 281 (extend db-config-backed generation to all four generators), ADR 280
  (comprehensive db-config-backed generation + read-only materialize smoke), ADR 272 (v60 config registry).

## Context

ADR 281 shipped (PR #68, merged) the gated core + per-kind descriptor registry that wires all four
generators — `comprehensive`, `model_controls`, `monthly`, `probability` — into the DB-config-backed
generation path, exposed via the CFR CLI and the operator UI route. Its evidence was unit/integration
tests plus the full CFR suite; the only run against *reality* to date was ADR 280's **read-only
materialize smoke** for comprehensive. No generator had ever produced a package end-to-end consuming the
**live** config snapshot against the **real** tropical data root.

This ADR records that validation. It is an evidence exercise — **no production source changed**.

## Decision

Run each of the four kinds **twice** against the live config DB (read-only) and the real data root,
in isolated work roots — once via the CFR CLI (`forecast-db-config-backed-generate`) and once via the
operator UI route (`POST /api/forecast/runs/db-config`, `X-HB-UI-Role: operator`) — and prove three
things per run plus one top-level invariant:

1. **Config genuinely consumed** — `config_snapshot_consumed=true`, `consumed_config_domains` equals the
   expected per-kind set, `fidelity_gate.passed=true`, snapshot = the live 194-item
   `tropical-phase16-live-config-20260619T085305Z` on schema v61.
2. **Read-only discipline** — each report's `safety` block shows `live_db_written=false`,
   `live_db_opened_read_only=true`, `live_db_migrated/imported=false`, `source_config_mutated=false`;
   the run's `live_db_integrity` shows `unchanged=true`, `drift=[]`, `preflight_stable=true`.
3. **UI redaction** — every operator-path summary passes `find_redaction_leaks == []`.
4. **Top-level mutation proof** — an external baseline-vs-final fingerprint of the live DB main file
   (size + mtime_ns + **sha256**) + `PRAGMA data_version` + `-wal`/`-shm`, captured before the first run
   and after the last, must be byte-identical — independent of the runs' own self-reports.

## Outcome

All four kinds **generated cleanly (rc 0 / HTTP 200, `status=generated`)** on both surfaces. Every
per-kind assertion held; `consumed_config_domains` matched exactly
(`comprehensive`→controls+model_controls+project, `model_controls`→model_controls,
`monthly`→controls+model_controls+staffing+project, `probability`→owner_sov_crosswalk+project).
Probability used the deterministic defaults `runs=10000, seed=20260614`. The UI summaries and list were
all redaction-clean.

**The live DB was byte-exact unchanged** across all eight runs: main sha256 identical
(`99614d4c…77645a`), `data_version` unchanged (2→2), and even `-wal`/`-shm` byte-identical — the DB
stayed fully quiescent. No rc-3 refusals occurred (all predecessor packages present; DB quiescent);
had any predecessor been missing or the DB non-quiescent, the run would have refused (rc 3) and that
would be recorded as a finding, not worked around.

## Discipline / notes

- Data root resolved to the project `default_data_root`, which equals `LIVE_ROOT` (the `2026-June`
  tropical input dir). Generators read it read-only; output packages were written only to `/tmp` work
  roots outside it. Work-root containment guards (live root / data root / source config / live-DB dir)
  were satisfied by choosing `/tmp` roots.
- The UI path was driven by a **fresh** app instance on a non-default port with the opt-in + roots set
  via **env only** (no persisted `forecast_runtime_config.json` write); the pre-existing dev server and
  the live config DB were untouched.
- Raw CLI reports are path-saturated and stored as-is in the audit bundle; the redaction gate applies to
  UI payloads, captured and asserted separately.

## Evidence

`docs/evidence/forecast-ui-db-config-live-proof-all-kinds/20260621T131846Z/` — README (summary tables),
`baseline_live_db.json` / `final_live_db.json`, `data_root_inventory.txt`, `snapshot_selection.txt`,
`db_schema_version.txt`, four `cli_<kind>_report.json`, four `ui_<kind>_summary.json` +
`ui_list_runs.json`, and `package_manifests.txt`.

## Consequences

The DB-config-backed generation path is now validated against live data for all four generators on both
the CLI and operator UI surfaces — a promoted config snapshot demonstrably drives every generator while
the live DB stays read-only and unchanged. Deferred (separate, authorized work): a true read-only live
*execution* cutover, model engines (Phase I), production hardening (Phase J), and a real authorized live
config promotion.
