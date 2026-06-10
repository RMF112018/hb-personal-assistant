# Daily Brief Usefulness Repair — Rebaseline (Prompt 00)

Package: `docs/planning/daily-brief-usefulness-repair-package/` (v1.0.0)
Generated as part of the single-shot local-agent implementation run.

## Repo Truth

| Item | Value |
|---|---|
| Implementation branch | `fix/daily-brief-usefulness-repair` |
| Base | `main` @ `dbff6e89b` (HEAD at branch creation) |
| `origin/main` | `dbff6e89b` (in sync) |
| Schema version (migrator) | `LATEST_SCHEMA_VERSION = 45` |
| Working tree | clean except untracked `docs/planning/*` package dirs |

Note: the prior session branch `experiment/phase-10-top3-local-model-agent-convergence`
(`afaa3a24`) is an **ancestor of** `main` (`main..HEAD` empty); `main` already contains all
Phase 10 second-brain `local_ai` code, the project alias resolver, and the V45 schema. Branching
from `main` is correct and complete.

## Audit Basis (safe scorecard, from package reference)

Schema V45. Both DB integrity checks passed in the private audit.

| Metric | Value |
|---|---:|
| calendar_project_resolution_rate | 0.0 |
| calendar_near_term_event_count | 8 |
| calendar_unassigned_project_like_count | 8 |
| procore_open_signal_count | 5,866 |
| procore_due_soon_count | 0 |
| procore_recent_signal_count | 1,888 |
| procore_aggregate_sludge_count | 3,592 |
| daily_brief_candidate_count | 0 |
| candidate_source_ref_coverage | 0.0 |
| project_key_coverage | 0.0 |

## Production DB identification (read-only, for Prompt 06)

`PathPolicy().get_db_path()` resolves to the plain app-support root:
`~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`.
Read-only probe confirms this DB is the audit DB (schema=45, open Procore signals = **5,866**,
calendar events = 161) — it matches the audit scorecard. The `(Dev)` and `(Dev) (Dev)` roots do
**not** match (0 open Procore signals). DB-copy validation will `.backup` from the plain root only.

## Root-cause refinement (from repo-truth exploration)

- A project alias resolver already exists and works (`project_aliases.py::resolve_project()` +
  `resources/config/project_aliases.seed.yaml`: TWN→tropical, Wellington→the-wellington,
  Hilltop/Alton Hilltop→alton-hilltop-pbg, PGA→pga-modern-garage) and is already wired into
  `calendar_prep.py`. The 0.0 calendar resolution is downstream of **candidates = 0**. Priority 1's
  real gap is **category classification** (project vs internal/PTO/training/needs_review).
- Source-ref coverage 0.0 because the candidate writers never persist `candidate_source_refs`
  (the table + idempotent `upsert_candidate_source_ref()` exist but are unused by these stages).
- Procore aggregate "sludge" rows are emitted on purpose by `procore_digest.py`
  (`"{count} open {signal_type} signals"`), with no ranking and no `why_today`.

## Schema decision

Reuse V45 (`daily_brief_action_candidates` + `candidate_source_refs`); internal categories encoded
as `project_key` sentinels; no migration required. Recorded in the architecture note at closeout.

## Safety posture

No production DB mutation. No external writeback. No cloud model route. DB-copy validation only,
outputs under `/tmp`. Evidence contains safe counts / redacted summaries only — no raw DB content.
