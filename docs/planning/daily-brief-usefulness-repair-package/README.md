# Daily Brief Usefulness Repair Package

Package version: `v1.0.0`  
Target repository: `RMF112018/hb-personal-assistant`  
Local path: `/Users/bobbyfetting/hb-personal-assistant`  
Target branch: `fix/daily-brief-usefulness-repair`  
Execution mode: single-shot local-agent implementation package

## Objective

Repair the production daily-brief pipeline so a technically successful run cannot produce an operator-useless brief.

The implementation must address all five priorities:

1. Calendar project alias resolution before calendar-prep candidate persistence.
2. Procore signal ranking and aggregate-backlog suppression.
3. Daily-brief candidate projection so deterministic sections are populated from real source rows.
4. Source-ref gating before model-facing selection.
5. Usefulness/success gates across daily-run status, browser HTML, Obsidian output, and model synthesis.

This is implementation work. Modify repo code and tests as needed. Do not mutate Bobby's production DB during validation. Use DB copies and `/tmp` output roots for live proof.

## Audit Basis

The package is based on Bobby's private DB-usefulness audit of a production DB copy.

| Metric | Value |
|---|---:|
| Schema version | 45 |
| Calendar project resolution rate | 0.0 |
| Calendar near-term event count | 8 |
| Calendar project-like unassigned event count | 8 |
| Procore open signal count | 5,866 |
| Procore due-soon count | 0 |
| Procore recent signal count | 1,888 |
| Procore aggregate-sludge count | 3,592 |
| Follow-up open count | 0 |
| Email model-ready thread count | 0 |
| Email enrichment pending count | 0 |
| Daily-brief candidate count | 0 |
| Candidate source-ref coverage | 0.0 |
| Project key coverage | 0.0 |

Family verdicts:

- `calendar`: `blocked_by_project_resolution`
- `procore`: `blocked_by_ranking`
- `daily_brief_candidates`: `missing`
- `candidate_source_refs`: `blocked_by_empty_source`
- `followups`: `blocked_by_empty_source`
- `email`: `blocked_by_empty_source`

Root cause:

`selection_ranking_fix`: the DB has useful source data, but the daily brief is feeding the model unranked Procore sludge, unassigned calendar rows, and no persisted/validated daily-brief candidate layer.

## Non-Goals

Do not:

- Replace the local model.
- Tune only the prompt and call the issue fixed.
- Add cloud model routes.
- Add external writeback.
- Send email, create drafts, mutate calendars, mutate Graph, mutate Procore, or mutate MCP/external systems.
- Run source refresh against live systems as part of validation.
- Mutate the production SQLite DB for proof.
- Persist raw prompts/responses/bodies/URLs/tokens into repo evidence.
- Make the scheduled 5 AM job active as proof. Manual copy-DB validation is enough.

## Hard Safety Rules

- Use `sqlite3 "$PROD_DB" ".backup '$AUDIT_DB'"` for production DB snapshots.
- Use copied DBs for all apply-mode validation.
- Use `/tmp/...` output roots for browser/status/Obsidian proof.
- Preserve all no-writeback guardrails.
- Preserve all raw-content boundaries:
  - raw local content may appear only in approved private-local surfaces when explicitly requested.
  - status JSON, evidence, logs, source refs, and persisted candidates must remain redacted/hash-only.
- If a validation run needs `--apply`, it must target a DB copy and `/tmp` output roots.
- If any guard/writeback/raw persistence counter is nonzero, stop and hand off failure evidence.
- If any rendered output contains forbidden strings, stop and hand off failure evidence.
- If any production DB hash changes during validation, stop.

## Desired Product Behavior

A daily brief may report `success` only if it contains at least one operator-useful deterministic section with concrete, ranked, source-linked items.

Operator-useful means:

- project-resolved or explicitly categorized as `internal/company`;
- source-linked;
- action-ranked;
- not just aggregate counts;
- tied to today/tomorrow or recent change when applicable;
- has a clear "why this matters today";
- consistent between deterministic sections and model-enriched synthesis.

If the pipeline cannot produce such content, it must return `partial` or `degraded`, preserve the last successful brief, and clearly explain which gate failed.

## Branch Strategy

Start from current `main`, unless repo truth indicates a newer integration branch is required.

```bash
cd /Users/bobbyfetting/hb-personal-assistant
git fetch origin
git checkout main
git pull --ff-only
git checkout -b fix/daily-brief-usefulness-repair
```

If the branch already exists, inspect it before deciding whether to reset, continue, or create a new branch.

## Required Prompt Sequence

Execute the prompts in order. Each prompt should end in a focused commit unless a stop condition triggers.

1. `prompts/00_REPO_TRUTH_REBASELINE_AND_BRANCH.md`
2. `prompts/01_CALENDAR_PROJECT_ALIAS_RESOLUTION.md`
3. `prompts/02_PROCORE_SIGNAL_RANKING_AND_SUPPRESSION.md`
4. `prompts/03_DAILY_BRIEF_CANDIDATE_PROJECTION.md`
5. `prompts/04_SOURCE_REF_GATE_AND_USEFULNESS_CONTRACT.md`
6. `prompts/05_SURFACE_INTEGRATION_AND_SUCCESS_GATES.md`
7. `prompts/06_DB_COPY_LIVE_VALIDATION.md`
8. `prompts/07_FINAL_HANDOFF.md`

## Expected Commit Shape

Recommended commit sequence:

1. `docs(second-brain): add daily brief usefulness repair baseline`
2. `fix(second-brain): resolve calendar project aliases for brief candidates`
3. `fix(second-brain): rank Procore signals for daily brief usefulness`
4. `fix(second-brain): project source-linked daily brief candidates`
5. `fix(second-brain): gate model synthesis on source-linked useful context`
6. `fix(second-brain): enforce daily-run usefulness status gates`
7. `test(second-brain): prove daily brief usefulness repair on DB copy`
8. `docs(second-brain): add daily brief usefulness repair handoff`

Adjust commits to repo truth. Do not over-fragment if smaller scoped commits are cleaner.

## Likely Files and Modules

Inspect repo truth first. Likely areas include:

- `src/hb_assistant/construction/second_brain/local_ai/calendar_prep.py`
- `src/hb_assistant/construction/second_brain/local_ai/pipeline.py`
- `src/hb_assistant/construction/second_brain/local_ai/daily_run.py`
- `src/hb_assistant/construction/second_brain/local_ai/daily_brief_llm_synthesis.py`
- `src/hb_assistant/construction/second_brain/local_ai/daily_run_html.py`
- `src/hb_assistant/construction/second_brain/local_ai/daily_brief_intelligence.py`
- `src/hb_assistant/construction/second_brain/local_ai/procore*`
- `src/hb_assistant/construction/second_brain/daily_brief/*`
- `src/hb_assistant/cli/second_brain.py`
- `src/hb_assistant/store/migrator.py`
- `resources/config/*project*`
- `resources/config/local_model_task_routing.seed.yaml`
- `tests/test_phase_10*.py`
- daily-run / daily-brief / Procore / calendar / source-ref tests
- `docs/architecture/`
- `docs/evidence/`

Do not assume these are the only files.

## Schema Strategy

Do not assume a migration is required.

Preferred path:

- Reuse existing V45 tables:
  - `calendar_event_raw_content`
  - `calendar_project_match_candidates`
  - `procore_action_signals`
  - `procore_record_timeline_events`
  - `procore_live_record_change_events`
  - `daily_brief_action_candidates`
  - `daily_brief_source_refs` or `candidate_source_refs` depending on existing repo contract
  - `daily_brief_runs`
  - `daily_brief_handoff_lines`
- If existing tables cannot support source-linked brief projection, stop and document a minimal additive migration proposal before implementing it.
- Any migration must be additive, idempotent, guarded, tested on a fresh DB and a DB copy, and justified against existing V45 schema.

## Implementation Details by Priority

### Priority 1 — Calendar Project Alias Resolution

Problem:

Near-term calendar rows exist with useful subjects and attendee counts, but all 8 project-like meetings for the failed brief were `__unassigned__`.

Required behavior:

- Calendar prep must resolve obvious project aliases before candidate persistence or deterministic brief projection.
- The resolver must distinguish:
  - project aliases;
  - internal/company events;
  - PTO/training/admin events;
  - unknown/needs-review.
- Do not force low-confidence mappings into project facts. Low-confidence mappings should become `project_key = "__needs_review__"` or equivalent review-safe status.

Initial alias expectations from audit:

| Token/context | Expected behavior |
|---|---|
| `Wellington` / `Pre-Submission Bid Review - The Wellington Homes` | resolve to `the-wellington` if repo project truth supports it |
| `Hilltop` / `Alton Hilltop` | resolve to `hilltop` or `alton-hilltop-pbg` based on repo truth |
| `TWN` / `TWN OAC` / `TWN RFI/Submittal` | resolve only after repo-truth mapping; likely Tropical/Tropical World but do not guess |
| `Financial Forecast` | classify as `internal/company` or needs-review, not project unknown |
| `PTO` | classify as `internal/time_off` |
| `Training` | classify as `internal/training` |

Acceptance:

- Synthetic tests cover alias, internal, PTO, training, ambiguous, and unknown cases.
- DB-copy proof shows near-term project-like calendar items no longer all land as `__unassigned__`.
- Low-confidence mappings remain review-safe.
- No raw body output is needed.

### Priority 2 — Procore Signal Ranking and Aggregate Suppression

Problem:

The brief surfaced giant aggregate counts like 1,265 unanswered inspection items and 1,157 observation-required inspection items. The audit found 5,866 open Procore signals, 0 due soon, and 3,592 aggregate-sludge rows.

Required behavior:

- Build a Procore daily-brief ranking/read-model layer.
- Promote signals that are:
  - due soon;
  - recent;
  - high/critical;
  - owner-linked;
  - source-change/timeline-linked;
  - financially material;
  - newly observed since last successful brief;
  - linked to project-critical workflow.
- Suppress or demote aggregate backlog groups when:
  - count is high;
  - no due date;
  - not recent;
  - no owner;
  - not change-linked;
  - no "why today";
  - type is semantically closed/resolved.
- `observation_closed` must not appear as an open action unless repo truth proves an unresolved downstream implication.

Acceptance:

- Synthetic tests cover due-soon, recent, owner-linked, high-critical, stale aggregate, and closed-as-open cases.
- DB-copy proof shows top Procore daily-brief rows are no longer dominated by aggregate sludge.
- Aggregate counts may appear only in diagnostics/appendix as "suppressed backlog", not executive priorities.

### Priority 3 — Daily-Brief Candidate Projection

Problem:

The DB has source rows and `daily_brief_source_refs` / handoff lines, but `daily_brief_action_candidates` had 0 target-date rows, causing deterministic sections to be empty while model synthesis still produced claims.

Required behavior:

- Implement/repair deterministic candidate projection for the daily brief.
- The projection must produce row objects for:
  - calendar prep / meeting prep;
  - ranked Procore risks/actions;
  - follow-up/watch/enrichment rows when available;
  - data gaps and project-resolution warnings.
- Each row must include:
  - stable candidate id;
  - brief date;
  - section;
  - title/redacted title;
  - project key or internal category;
  - urgency/priority;
  - why-it-matters-today;
  - recommended next action;
  - confidence or quality score;
  - source-ref link(s);
  - safety/data-quality flags.
- Do not make model-only bullets the source of truth. Model synthesis should consume deterministic rows and summarize them.

Acceptance:

- Synthetic tests prove projection creates rows from calendar and Procore inputs.
- DB-copy proof against the audit fixture date creates nonzero daily-brief candidate rows on the copied DB.
- Deterministic sections no longer say zero when source rows exist.
- Projection is idempotent on the copied DB.

### Priority 4 — Source-Ref Gate and Model-Facing Contract

Problem:

Candidate source-ref coverage was 0.0, while the model emitted source ids over lower-level rows. A daily brief cannot be trustworthy without source-linked candidate context.

Required behavior:

- Define a model-facing brief context contract.
- No model-enriched synthesis may claim a meeting, Procore risk, follow-up, or action unless the deterministic candidate has source refs.
- Candidate source ref coverage must be computed and included in status.
- If coverage is below threshold:
  - degrade the run;
  - withhold model synthesis or mark it degraded;
  - preserve last successful brief;
  - show an operator-legible data-quality failure.

Minimum threshold:

- For `success`: source-ref coverage must be 100% for surfaced executive/top-priority rows.
- For non-executive appendix rows: allow explicitly labeled diagnostics with missing refs only if not used by synthesis.

Acceptance:

- Tests prove missing refs degrade/withhold.
- Tests prove source-linked rows pass.
- Tests prove model synthesis cannot reference withheld rows.
- Status JSON includes source-ref coverage and usefulness gate outcome.
- Browser/Obsidian output labels degraded/missing-source state clearly.

### Priority 5 — Usefulness / Success Gates

Problem:

The daily-run status reported success even though the produced brief was internally contradictory and operator-useless.

Required behavior:

Add a usefulness gate after deterministic projection and before final success.

A fresh daily-run can return `success` only if:

- at least one operator-useful section is nonempty;
- deterministic sections are coherent with model synthesis;
- model-enriched bullets are source-linked;
- project-like calendar meetings are not all unresolved;
- Procore top rows are not dominated by aggregate sludge;
- no section contradiction exists;
- no forbidden raw/egress content is found.

If not:

- return `partial` or `degraded`;
- preserve last successful browser path;
- write attempted/degraded brief only if safe;
- status JSON explains `usefulness_gate_failed`;
- do not update `daily-brief-latest.html` as successful.

Acceptance:

- Unit tests cover success, partial, degraded, and failure.
- Live DB-copy proof on the audit date must not return `success` until repaired rows pass the gates.
- After repairs, DB-copy run should produce a brief with real meeting titles, project/internal categories, ranked Procore rows or a clear suppression note, and nonzero deterministic sections.

## Validation Requirements

At minimum run:

```bash
python -m compileall src tests
pytest -q \
  tests/test_phase_10_daily_run*.py \
  tests/test_phase_10_daily_brief*.py \
  tests/test_phase_10_procore*.py \
  tests/test_phase_10_calendar*.py \
  tests/test_phase_10*_source*.py
```

Adjust exact test names to repo truth.

Run focused new tests:

- calendar alias resolver
- Procore ranking/suppression
- daily-brief candidate projection
- source-ref gate
- usefulness gate
- browser/Obsidian degraded labeling if touched
- status JSON shape
- no raw/forbidden output scan

Run changed-file lint/type checks if repo supports them:

```bash
ruff check <changed files>
mypy <changed python files>
```

Document pre-existing unrelated failures. Do not silently broaden scope to fix unrelated failures.

## DB-Copy Live Proof

Use this pattern:

```bash
TS="$(date +%Y%m%d-%H%M%S)"
PROD_DB="$HOME/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"
AUDIT_ROOT="/tmp/daily-brief-usefulness-repair-$TS"
AUDIT_DB="$AUDIT_ROOT/prod-copy.sqlite"
TEST_VAULT="$AUDIT_ROOT/vault"
TEST_HTML="$AUDIT_ROOT/html"
TEST_STATUS="$AUDIT_ROOT/status"

mkdir -p "$AUDIT_ROOT" "$TEST_VAULT" "$TEST_HTML" "$TEST_STATUS"
sqlite3 "$PROD_DB" ".backup '$AUDIT_DB'"
sqlite3 "$AUDIT_DB" "PRAGMA integrity_check;"
sqlite3 "$AUDIT_DB" "PRAGMA quick_check;"

BEFORE="$(shasum -a 256 "$PROD_DB")"

.venv/bin/hb-assistant second-brain daily-run run \
  --apply \
  --raw \
  --write-obsidian \
  --confirm-vault-write \
  --vault-brief-dir "$TEST_VAULT" \
  --browser-output-dir "$TEST_HTML" \
  --status-dir "$TEST_STATUS" \
  --db "$AUDIT_DB" \
  --json | tee "$AUDIT_ROOT/daily-run-copy-apply.json"

AFTER="$(shasum -a 256 "$PROD_DB")"
printf '%s\n%s\n' "$BEFORE" "$AFTER" > "$AUDIT_ROOT/prod-db-hash-before-after.txt"
```

Expected after implementation:

- production DB hash unchanged;
- copied DB may mutate in apply mode;
- browser/status/Obsidian outputs only under `/tmp`;
- status shows usefulness-gate metrics;
- deterministic sections no longer contradict source availability;
- rendered brief is safe and operator-useful.

## Evidence Requirements

Create evidence under:

`docs/evidence/daily-brief-usefulness-repair/`

Recommended structure:

```text
docs/evidence/daily-brief-usefulness-repair/
  00-rebaseline/
  01-calendar-alias-resolution/
  02-procore-ranking/
  03-candidate-projection/
  04-source-ref-gates/
  05-usefulness-gates/
  06-db-copy-live-proof/
  07-final-handoff/
```

Do not store raw private DB output in repo evidence. Repo evidence should contain:

- safe row counts;
- redacted summaries;
- hash proofs;
- test logs;
- status JSON with private paths redacted;
- forbidden-string scan results;
- production DB unchanged proof;
- screenshots only if scrubbed and safe.

Private raw-local outputs, if needed, stay in `/tmp` and are referenced only by path in final handoff.

## Stop Conditions

Stop and hand off evidence if:

- production DB cannot be backed up;
- copied DB integrity check fails;
- schema version below V45;
- any validation mutates production DB;
- any external writeback occurs;
- any email send/draft/calendar mutation/Procore write occurs;
- cloud model route is introduced;
- raw prompt/response/body/url/token leaks into evidence/status/logs;
- guard columns become nonzero;
- daily-run reports success while deterministic sections remain empty;
- source-ref coverage for executive rows remains below 100%;
- calendar project-like items remain all unassigned without degradation;
- Procore executive rows remain dominated by aggregate sludge;
- tests fail because of the new changes;
- branch is dirty with unrelated files you cannot isolate.

## Final Handoff Requirements

The final response must include:

1. Branch and HEAD.
2. Base/main relationship.
3. Commit list.
4. Files changed.
5. What changed per five priorities.
6. Schema decision.
7. Test results.
8. DB-copy live proof result.
9. Production DB unchanged proof.
10. Safety/forbidden scan.
11. Daily brief before/after summary.
12. Known limitations.
13. Stop conditions, if any.
14. Exact manual verification commands.
15. Merge recommendation.
