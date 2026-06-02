# 00 — Repo-Truth Rebaseline (Phase 08A Prompt 00)

**Audit-only.** No source, schema, CLI, README, or validation-matrix files were edited. The sole
deliverables of this prompt are this file and `01-phase-07d-gap-audit.md`. This run reproduces the
Phase 08A package's validation matrix **locally**, closing the limitation declared in the package's
`02_REPO_TRUTH_AUDIT_SUMMARY.md` ("this package did not run local tests, migrations, CLI commands…").

## Audit metadata

| Field | Value |
|---|---|
| Date | 2026-06-02 |
| Branch | `main` |
| HEAD | `41d896e5fda13affdc0aacf360ca360c240b8464` |
| Working tree at start | clean (only untracked `.claude/`, `.code-graph/`) |
| Phase 07D target commit (`00_PACKAGE_MANIFEST.md`) | `41d896e…` — **identical to live HEAD** |
| Prior baselines | 07A `3cf1652bf55303ceea25b2bbc6b5b1785111a335` · 07B `748ed7e6519ada0a74d09376f2d2fe353627ac2b` · 07C `733ffedae071ce6a766a33fcd9233205364b8013` |
| Package version | `1.3.0` (`hb-assistant --version`) |
| Python | 3.14.5 (`.venv`) |
| Schema head | **V25** (`construction-agent validate` → `schema_version=25`) |

## Validation matrix — commands, exit codes, results

All commands run inside `.venv`. Exit codes captured.

| Command | Exit | Result |
|---|---:|---|
| `python -m compileall src tests` | 0 | clean |
| `ruff check .` | 0 | `All checks passed!` (scope partial-by-config — see note) |
| `mypy src` | 0 | `Success: no issues found in 190 source files` (scope partial-by-config — see note) |
| `pytest -m "not live and not integration and not manual"` | 0 | **2226 passed, 1 deselected** on repeat (deterministic-green). One earlier run produced a single intermittent flake — see "Test-suite observations". |
| `hb-assistant construction-agent validate --json` | 0 | 4/4 checks ok; `schema_version=25`; 6 projects / 14 sources; review rules v1 (25 rules, threshold 0.7); model routing v1 (default `llama3.2:1b`). Guardrails: external `read_only`, writeback `none`. |
| `hb-assistant construction-agent data-quality table-inventory --json` | 0 | 116 contract tables; `read_only:true`. Status breakdown + reconciliation below. |
| `hb-assistant construction-agent data-quality no-writeback-proof --json` | 0 | `proof_passed=true`; `repo_sha=41d896e…`; `schema_version=25`; scans 07A + 07B + 07C + 07D module arms. |
| `hb-assistant construction-agent data-quality phase-07d-gates --json` | 0 | `ok=true`; source-scope safe counts: OneDrive explicit-subset 0 / explicit-all-folders 4 / implicit-root-blocked 0; SharePoint approved-all-nested 10. |

### `table-inventory` summary_by_status

`operational_populated` 66 · `operational_empty_expected` 27 · `evidence_only` 9 ·
`operational_empty_blocking` 9 · `legacy_superseded` 4 · `placeholder_deferred` 1.

Reconciliation: `in_db_not_in_contract` = []; `in_contract_not_in_db` =
`procore_sync_errors`, `procore_sync_runs`, `procore_sync_watermarks`, `procore_synced_entities`
(expected — Procore live-sync tables are not materialized in local-only mode).

### `no-writeback-proof` 07D module coverage (confirms Phase 07D arm exists)

`scanned_modules_07d` = `relationships/cross_source_substrate.py`, `relationships/contracts.py`,
`meeting_prep/brief_builder.py`, `issue_history/issue_history_builder.py`,
`risk_digest/risk_digest_builder.py`, `aging_exposure/aging_exposure_builder.py`,
`correspondence/correspondence_context.py`, `obsidian/cross_source.py`, … . The `report.phase`
string is `Phase 07A Prompt 08 + Phase 07B Prompt 12 + Phase 07C Prompt 12 + Phase 07D Prompt 13`.

## CLI surface confirmation

`construction-agent data-quality --help` subcommands present:
`project-coverage`, `source-record-map`, `relationships`, `marts`, `obsidian`, `gates`,
`no-writeback-proof`, `table-inventory`, **`phase-07d-gates`**.

- **Absent:** `phase-07d-no-writeback-proof` (drives gap G-07D-02), `phase-08a-gates`,
  `phase-08a-no-writeback-proof`.
- **Absent:** any `second-brain` Typer group (Phase 08A runtime not yet built).

Confirmed-present Phase 07D CLI surfaces (per package `02_…`): `relationships build/status/promote`,
`meeting-prep build/status`, `issue-history build/status`, `risk-digest build/status`,
`aging-exposure build/status`, `correspondence context/status`, `cross-source obsidian/status`,
`data-quality phase-07d-gates`.

## Validation-scope honesty note (feeds G-07D-07)

`ruff check .` and `mypy src` report clean, but scope is **intentionally partial** per
`pyproject.toml` (`[tool.ruff] extend-exclude` / `per-file-ignores`, `[[tool.mypy.overrides]]` with a
global `hb_assistant.*` error-ignore). `mypy` checked 190 source files and emitted
`unused section(s): module = ['hb_assistant.retrieval.context']`. A green ruff/mypy here is **not**
whole-repo strictness; Phase 08A modules must opt into strict checks (tracked as G-07D-07).

## Test-suite observations

1. **Deterministic-green.** The default-safe subset is **2226 passed, 1 deselected**, reproduced on
   multiple consecutive runs. `pytest-randomly`/`pytest-xdist` are **not** installed (pytest 9.0.3
   only); collection order is deterministic.
2. **One intermittent flake (not a leak).** A single earlier full-suite run failed
   `tests/test_cross_source_obsidian.py::test_no_raw_content_in_notes_and_report`: the test's
   `_LEAK` guard regex (the case-insensitive `eyJ` JWT-header heuristic) matched a 3-char substring
   `eyj` in the JSON-serialized render report. Characterization:
   - The test seeds **only synthetic data** (ids `c0`/`m0`/`r0`, project `tropical`, risk summary
     `{"count": 2}`) — no URLs, tokens, secrets, or raw content.
   - The same file passes **7/7 in isolation**; the failure did not recur in 5 subsequent full runs.
   - The exact production render path (`ObsidianCrossSourceRenderer.render(apply=True)`) was
     reproduced **60×** in-process and across **81 fixed `PYTHONHASHSEED` values** in fresh
     processes — **0 matches**. The match arises only from rare cross-test state contamination, not
     from the render output itself.
   - The production guard CLI `data-quality no-writeback-proof` returns `proof_passed=true`, and the
     test's `_assert_guards_zero` (all eight V25 guard CHECK columns = 0) holds.
   - **Conclusion:** this is a test-isolation / false-positive-regex robustness defect, **not** a
     runtime or guardrail regression and **not** a real content leak. Logged as a new gap in
     `01-phase-07d-gap-audit.md` (G-07D-08).
3. **Evidence-artifact churn.** Running the suite/CLI from the repo root regenerates several tracked
   `docs/evidence/**` files (timestamp/path refresh: phase-06-email, phase-07a-data-quality,
   mvp-local-runtime, remediation). These side-effects were **reverted** (`git checkout --`) so this
   audit adds only the two Phase 08A evidence files. Minor test-hygiene observation; non-blocking.

## Guardrail attestation

- Read-only against all external systems; **no** Microsoft 365 / Graph / SharePoint / OneDrive /
  Outlook / Calendar / Procore / Obsidian / SQL writeback was performed.
- No raw email/document/calendar bodies, signed/download URLs, tokens, secrets, or private payload
  values were captured into this evidence. All command outputs recorded here are metadata/summary
  counts and pass/fail status only.
- No Microsoft 365, Procore, or vault source-note mutation. The tree contains only the two new
  Phase 08A evidence files after this run.
