# Phase 07B Prompt 12 — No-Writeback / No-Secret / No-Raw-Body Proof (redacted)

Date: 2026-05-31 · Branch: `main` · Repo SHA at start: `faa1ccc` · Package `1.3.0` ·
Schema head V23.

Extends the `data-quality no-writeback-proof` prover so the single authoritative command
proves both Phase 07A **and** Phase 07B (calendar/email/thread/candidate): the 10 07B
modules, the V11/V14/V23 guard CHECK columns, the persisted content of the 07B tables, and
the 07B evidence dir — all folded into `proof_passed`, fail-closed. Read-only; findings are
pattern labels and `table.column` locations only — never the value. All values below are
structural facts only.

## Files changed

- `src/hb_assistant/construction/data_quality/safety.py` (07B module/guard/content/evidence
  scans + the six `*_07b` checks_detail keys + verdict folding)
- `src/hb_assistant/construction/calendar/event_indexer.py` (`fields.update({...})` →
  explicit assignments so the AST mutation scan stays clean — behavior identical)
- `tests/test_phase07b_no_writeback_proof.py` (new — 4 tests)
- `docs/architecture/29-phase-07b-no-writeback-proof.md` (new)
- this evidence file

## Preflight (HEAD faa1ccc, all exit 0)

`git status --short` (clean except untracked `.claude/`), `python -m compileall -q src tests`,
`ruff check .` (All checks passed!), `mypy src` (Success), `pytest -m "not live and not
integration and not manual"` (0 failed), `tests/test_data_quality_safety_proof.py` +
`tests/test_mutation_lockout.py` green.

## Post-implementation local validation (all exit 0)

| Command | Result |
| --- | --- |
| `python -m compileall -q src tests` | exit 0 |
| `ruff check .` | All checks passed! |
| `mypy src` | Success: no issues found in 164 source files |
| `pytest tests/test_phase07b_no_writeback_proof.py tests/test_data_quality_safety_proof.py tests/test_calendar_event_indexing.py -v` | 18 passed |
| `pytest -m "not live and not integration and not manual"` | 0 failed |
| `pytest tests/test_mutation_lockout.py` | passed (graph/ static no-write scan clean) |
| `hb-assistant construction-agent validate --json` | exit 0 |
| `hb-assistant procore validate --json` | exit 0 |
| `hb-assistant graph files status --json` | exit 0 |
| `hb-assistant graph mail status --json` | exit 0 |
| `hb-assistant graph calendar status --json` | exit 0 |
| `hb-assistant construction-agent data-quality gates --json` | exit 0 |
| `hb-assistant construction-agent data-quality no-writeback-proof --json` | exit 0 (proof_passed) |

`ruff format` is NOT enforced repo-wide; `ruff check .` is the authoritative lint gate and
passes. `ruff format` was not run.

The 4 unit tests cover: a clean pass that asserts all six `*_07b` keys **and** the 07A keys
passed with the 10 07B modules scanned and the guard probe listing the 07B tables; a
populated-store pass with a clean content scan; and two **fail-closed** cases — a raw email
address and a signed/`sig=` URL injected into a metadata-only 07B text column each flip
`proof_passed=false` via `sqlite_content_leak_scan_07b_tables`, and the offending value never
appears in the report.

## Live proof (real store, read-only)

`hb-assistant construction-agent data-quality no-writeback-proof --json`:

| Field | Value |
| --- | --- |
| proof_passed / no_raw_values_persisted | true / true |
| phase | Phase 07A Prompt 08 + Phase 07B Prompt 12 |
| scanned_modules_07b | 10 |
| static_writeback_scan_07b_modules | passed, 0 findings |
| no_http_client_or_mutation_imports_07b | passed, 0 findings |
| module_secret_scan_07b | passed, 0 findings |
| sqlite_guardrail_07b_tables | passed, 0 findings |
| sqlite_content_leak_scan_07b_tables | passed, 0 findings |
| evidence_output_scan_07b | passed, 0 findings |

Content-scanned 07B tables (live row counts): `calendar_event_index` (108),
`meeting_email_relationship_candidates` (117), `calendar_event_attendees` (1250),
`email_model_classifications` (40), `email_thread_summaries` (19),
`email_thread_summary_materialization_runs`, `calendar_crawl_runs`,
`calendar_project_match_candidates`. The emitted report contained no raw email address and no
`http(s)://` URL.

## Scope notes

- The prover is read-only and Graph-free; no Microsoft 365 mutation/writeback; no SQLite
  writes. No Phase 07D meeting-prep readiness is claimed (this proof is a prerequisite gate).
- **Closes the residual gap** noted in Prompts 06–11: the no-writeback / no-raw-body prover
  now covers the V11/V14/V23 calendar/email tables, the 07B modules, and the 07B evidence
  dir.
