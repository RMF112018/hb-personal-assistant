# Rebaseline — Deterministic-Fallback Status Repair

- Branch: `fix/daily-brief-deterministic-fallback-status`
- Base: `main @ 0db2993e` (contains the merged Daily Brief Usefulness Repair, schema V45).
- Prod DB identification (read-only): `PathPolicy().get_db_path()` = the V45 audit DB
  (5,866 open Procore signals) — backed up via `sqlite3 .backup` to `/tmp` for validation.

## Observed-before behavior (the bug)

After the usefulness repair, a DB-copy run produced an internally inconsistent run state:
`status: partial` while `partial: false`; brief banners "Partial — synthesis degraded or a stage
failed" + "DEGRADED — local-model synthesis unavailable; NOT counted as successful"; yet
`usefulness_gate.passed: true` (18 candidates, calendar resolution 1.0, source-ref coverage 1.0,
egress clean) and `model_enriched_intelligence.available: true, degraded: false`. The stable brief
path was not updated despite a usable deterministic brief.

Root cause: the synthesis-degraded path set `status="partial"` (while top-level `partial` tracked
`pipeline.partial`=False), conflating a deterministic-useful brief with degraded synthesis and a
genuinely unusable run. Scope: status/publishing/labeling only — no substrate/model/prompt changes.
