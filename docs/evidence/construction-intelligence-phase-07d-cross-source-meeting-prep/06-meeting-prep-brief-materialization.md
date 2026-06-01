# 07D Prompt 06 — Meeting-Prep Brief Materialization (Evidence)

Additive over schema **V25** (no migration). Materializes source-linked meeting-prep briefs into
`meeting_prep_brief_runs` + `meeting_prep_brief_sections` via a new `construction-agent meeting-prep`
sub-app.

## Preflight (repo truth)

- `git rev-parse HEAD` → `8cfd91b05a6aeb243af5e650933ea6dcca1904e1` (Prompt 05 HEAD).
- `git status --short` → clean (only untracked `.claude/`, `.code-graph/`).
- `python --version` → Python 3.12.11 (`.venv/bin/python3.12`); `hb-assistant --version` → `1.3.0`.
- Schema version → **25**; package version → `1.3.0`.
- Ancestry — all ancestors of HEAD: 07A `3cf1652…`, 07B `748ed7e…`, 07C `733ffed…`.
- Evidence folder present with `00`–`05`; this adds `06`.

## What changed

- **Engine** `src/hb_assistant/construction/meeting_prep/brief_builder.py` (+ `__init__.py`):
  `MeetingPrepBriefBuilder.build()` (dry-run default / `--apply`), eight policy section builders,
  deterministic-hash run/section ids, prerequisite gating via `meeting_prep_readiness`, and a
  read-only `meeting_prep_brief_status()`.
- **Store** `construction/store/repositories.py`: `list_cross_source_relationships` (promoted reader)
  + `upsert/list/count` for `meeting_prep_brief_runs` / `meeting_prep_brief_sections`.
- **CLI** `cli/construction.py`: `construction-agent meeting-prep build/status`.
- **Tests** `tests/test_meeting_prep_brief.py` (8).
- Reused unchanged: `data_quality/gates.py` (readiness), `relationships/contracts.py`, the V25 brief
  tables already present in `store/migrator.py`, and the existing
  `list_calendar_event_index`/`get_project_identity`/`list_cross_source_relationship_candidates`/
  `list_source_evidence_trails` readers.

## Honest design grounded in live-data truth

- `construction_project_identity` is **empty** → projects enumerated from the substrate (`tropical`);
  `project_context` degrades to `identity_resolved:false` + `unknown_project_identity` (no fabrication).
- All live calendar events have `project_key=NULL` → `meeting_context` reports 0 project-matched
  meetings + a flagged unmatched-upcoming count, never binding them to the project.
- `aging_items` / `risk_exposure_watchlist` are **deferred** (Prompt 07/09 and 08 not implemented):
  `available:false` + `deferred_source` flag, no synthetic items.

## Static + test validation (exit codes)

| Command | Result |
|---|---|
| `python -m compileall src tests` | exit 0 |
| `ruff check .` | exit 0 — All checks passed |
| `mypy src` | exit 0 — no issues in **180** source files |
| `pytest -m "not live and not integration and not manual"` | **2173 passed**, 1 deselected (exit 0) |

(Prompt 05 baseline 2165; +8 new brief tests.)

## CLI validation matrix (all exit 0)

`meeting-prep build` (dry-run), `meeting-prep build --apply`, `meeting-prep status`,
`construction-agent {validate, data-quality gates/no-writeback-proof/table-inventory}`,
`procore validate`, `graph files status/no-writeback-proof`, `graph calendar status`,
`graph mail status` — captured to `/tmp/p06/*.json` (ephemeral, not committed).

### Live `meeting-prep build` (project `tropical`)

| Run | mode | runs_written | sections_written | review_required | blocked |
|---|---|---|---|---|---|
| dry-run | dry_run | 0 | 0 (planned 8) | — | False |
| apply | apply | 1 | 8 | 3 | False |

- `by_section_kind` = all eight kinds × 1; `prerequisite_readiness.ready=true`.
- `meeting-prep status` → `runs=1`, `sections=8`, `materialized_runs=1`, `blocked_runs=0`,
  `review_required_sections=3`.
- **Blocked path** (tested on a fresh DB with no readiness injection): readiness computed = not ready
  → run `status="blocked"`, `sections_written=0`, `summary.blocked=True`, `ok=True`.

### Safety invariants (after live apply)

- No-raw-content regex (`https?://|@…|BEGIN:V|-----BEGIN|Bearer |eyJ`) over the serialized
  `build --apply` and `status` payloads → **no match**; per-test scan over run+section rows → clean.
- All eight guard `CHECK(… = 0)` columns stay 0 on both brief tables (asserted in tests).
- `data-quality no-writeback-proof` `proof_passed=true`; `graph files no-writeback-proof` `ok=true`.
- `table-inventory` `schema_version=25`, `contract_table_count=120` (no new tables).
- `data-quality gates` `meeting_prep_readiness_claim="ready"`, `ready=true` — unchanged.

## Test-path coverage (new file)

success (8 sections, matched + unmatched meeting counts, promoted recent-activity, guard columns 0);
prerequisite-blocked (status=blocked, 0 sections); review-required surfaced (section + run count);
deferred sections honest (`deferred_source`, no items); no-raw-content; idempotent apply (1 run / 8
sections on re-run); dry-run writes nothing; status coverage.

## Guardrails honored / stop conditions

- No external writeback / write scopes; no mutation beyond local SQLite brief tables; no schema change.
- No raw email/document/calendar content, signed/download URL, token, secret, prompt, or response
  persisted (no-raw test + both no-writeback proofs).
- Weak/model/sensitive relationships stay review-required; nothing auto-promoted.
- Advisory only — no final legal/contractual/claim/safety/financial determination emitted.
- Readiness not overstated: brief refuses (status=blocked) when prerequisites unmet;
  `auto_readiness_allowed=false`.
- No stop condition triggered; all validations classified and passing.

## Handoff

- **Changed:** new `meeting_prep` engine + `__init__`, 7 store methods, `meeting-prep` CLI sub-app,
  new brief test file, `docs/architecture/49-…md`, this evidence, README 07D ledger.
- **Gates pass/fail:** prerequisite gates unchanged and honest; live readiness `ready` → brief
  materialized; on a fresh DB the brief correctly blocks.
- **Next prompt allowed to proceed:** yes. Prompt 07 (project issue history) may build on these briefs;
  the brief substrate, deferred-section contract, and prerequisite gating are in place.
