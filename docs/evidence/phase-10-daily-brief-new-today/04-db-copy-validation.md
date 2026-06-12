# 04 — DB-copy validation (Phase 10 · 252 · New Today)

`new-today --apply` run against a **/tmp copy of the real production DB** (1.95 GB, observed at schema
V52). The copy was migrated to V54 (proving the migration applies on real prod data) and the digest
applied with a `--max-persist` cap. The production DB itself was never written — see
`12-prod-db-sha-unchanged.txt` (SHA-256 identical before/after) and `14-source-table-no-mutation-proof.json`.

## Resolved refresh window (deterministic contract)

- source: `run_markers`
- window: `2026-06-11T09:34:59.322263+00:00` → `2026-06-12T00:04:34.854172+00:00`
- rationale: Window spans the prior nightly refresh boundary (the most recent boundary at least 6h before the latest) to the most recent refresh completion.

The dev refresh loop writes many sync-run boundaries seconds apart; the window logic ignores
boundaries within one cycle-gap (6h) of the latest so the window spans the actual nightly cycle
(~14.5h here) instead of collapsing to sub-second and dropping the night's changes.

## Structural result (raw-free subset; real sentences withheld from evidence)

```json
{
  "command": "second-brain daily-brief new-today",
  "ok": true,
  "status": "degraded",
  "brief_date": "2026-06-12",
  "dry_run": false,
  "refresh_window": {
    "start_utc": "2026-06-11T09:34:59.322263+00:00",
    "end_utc": "2026-06-12T00:04:34.854172+00:00",
    "source": "run_markers",
    "rationale": "Window spans the prior nightly refresh boundary (the most recent boundary at least 6h before the latest) to the most recent refresh completion."
  },
  "lookahead_end_date": "2026-06-19",
  "gates": {
    "email_substrate_present": true,
    "email_actionable_count": 0,
    "email_degraded": true,
    "procore_demoted_count": 0,
    "total_events": 44,
    "by_family": {
      "email": 4,
      "calendar": 16,
      "procore": 24,
      "sharepoint": 0
    }
  },
  "model_layer": {
    "status": "skipped",
    "reason": "no_client"
  },
  "persist": {
    "persisted": true,
    "capped": false,
    "projected_inserts": 88,
    "max_persist": 5000,
    "persisted_events": 44,
    "persisted_refs": 44
  },
  "raw_safety_scan": {
    "clean": true,
    "categories": []
  },
  "guardrails": {
    "deterministic_authoritative": true,
    "model_advisory_only": true,
    "model_facts_immutable": true,
    "source_linked": true,
    "no_raw_persistence": true,
    "no_writeback": true,
    "dry_run_default": true,
    "apply_requires_max_persist": true,
    "apply_requires_temp_db": true
  },
  "db_indicator": [
    "explicit_db",
    "/tmp/hb-phase10-newtoday-1781259855/copy.sqlite"
  ],
  "diagnostic_labels": [
    "Email substrate present but no actionable follow-up derived"
  ]
}
```

44 source-linked events persisted (4 email, 16 calendar, 24 Procore); raw-safety clean;
`email_degraded` correctly fired because the in-window email substrate produced no newly-derived
actionable follow-up.
