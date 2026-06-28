# 11 — Known Limitations and Risks

## Scope limitations (by design, current state)

- **No PM-facing storytelling/narrative yet.** This package proves the engine + surfacing; it
  does not produce "what changed / why it matters" narrative. That is Phase 9.
- **No schedule-diff narrative yet.** Version-to-version diff storytelling is out of scope here.
- **No causal / root-cause claims.** Nothing in this package attributes delay causation; Phase 9
  must not either.
- **DCMA metric is evidence-based, not a certification.** No "certified DCMA compliant" or
  "true / P6 critical path" language is used or warranted.
- **No automatic recompute from UI/API.** The read endpoints and page are read-only; they never
  trigger CPM recomputation. CPM runs are produced by the chain runner, not by viewing.
- **Source-export evidence remains separate** from application-computed CPM (doc 05).
- **Calendar/offset modeling** is the engine's current implementation; this evaluation does not
  assert a full P6-equivalent calendar/lag model. Treat computed dates/float as the application's
  CPM, evaluated for internal consistency, not as a P6 re-derivation.

## Engine caveats carried into Phase 9 language

- **`computed_critical_outside_longest_path`** — 1312 activities classified critical vs a
  45-activity longest path; the divergence is flagged, not reconciled. Phase 9 narrative must
  carry this caveat and must not present a single flat "critical path = 1312 activities" claim
  (doc 06).
- **`graph_diagnostics` status label `not_implemented`** — the diagnostics-only run reports
  `cpm_recalculation_status = not_implemented` with 0 computed activities. This is correct
  (diagnostics scope), but the **label** is misleading in an executive context and should be
  reviewed/relabeled before executive-facing presentation (docs 00, 12).

## Runtime / configuration risk

- **`create_app()` DB binding.** `create_app()` without `db_path` leaves `app.state.db_path =
  None`, so a normal uvicorn factory launch shows `available: false` despite a populated DB.
  Evidence/runtime launches must use explicit `create_app(db_path=...)`, or a future patch must
  make `create_app()` honor `HB_ASSISTANT_DB_PATH` (docs 07, 08, 12).

## Repo-state risks

- **Working tree was dirty before this work** with unrelated obsidian_mcp WIP (doc 01). The
  eventual authorized commit must stage **only** `docs/evidence/schedule-cpm-engine-evaluation/`
  and must not pick up the obsidian_mcp files.
- **Stale `CLAUDE.md`** claims "No web service, frontend, or JS workspaces," which is no longer
  true (a frontend exists). Flagged for separate housekeeping; not changed here.
- **`scripts/test-schedule.sh` allowlist** is explicit, not auto-discovery — any future CPM test
  must be added to the bundle or it is silently uncovered.
- **Physical vs contract table count** (476 evidence-DB physical vs 477 lifecycle contract) is a
  recorded observation, not a CPM defect (doc 03).

## Validation noise (pre-existing, unrelated)

- Pre-existing frontend reds in `MyItemsPage`/`TodayPage` tests and 8 pre-existing eslint errors
  in untouched files exist on the base; they are unrelated to CPM. The CPM-specific frontend
  tests and the 5 CPM-touched files are clean (doc 09).
