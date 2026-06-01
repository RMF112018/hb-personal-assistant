# 07D Prompt 12 — 07D Data Quality Gates (Evidence)

Additive over schema **V25** (no migration). Completes the 07D gates wiring: the full twelve-field
`phase_07d_data_quality_gates` conformance report + four OneDrive/SharePoint source-scope safe
counts, exposed via `construction-agent data-quality phase-07d-gates --json`.

## Preflight (repo truth)

- `git rev-parse HEAD` → `bd631e786d9d9b44857d34dd23a87bd2d77ae622` (Prompt 11 HEAD).
- `git status --short` → clean (only untracked `.claude/`, `.code-graph/`).
- `python --version` → Python 3.12.11 (`.venv/bin/python3.12`); `hb-assistant --version` → `1.3.0`.
- Schema version → **25**; package version → `1.3.0`.
- Ancestry — all ancestors of HEAD: 07A `3cf1652…`, 07B `748ed7e…`, 07C `733ffed…`.
- Evidence folder present with `00`–`11`; this adds `12`.

## What changed

- **Engine** `construction/data_quality/phase_07d.py` (new): `evaluate_phase_07d_data_quality_gates`
  assembles the twelve contract fields (5 prereq gates reused via `evaluate_data_quality_gates`,
  4 coverage gates, `obsidian_output_safety`, `stale_unknown_warning_coverage`, and a 07D-scoped
  `no_writeback_no_secret_no_raw_content_proof`).
- **`gates.py`**: a module-level `source_scope_safe_counts(sources)` helper + `_gate_meeting_prep_
  prerequisite_status` now attaches the four named safe counts (the only `gates.py` change; no gate
  added/removed; existing statuses/counts unchanged).
- **`__init__.py`** export; **CLI** `data-quality phase-07d-gates` command.
- **Contract** `phase_07d_data_quality_gates.json`: additive `source_scope_safe_counts` field list.
- **Tests** `tests/test_phase_07d_data_quality_gates.py` (8).
- Reused: `evaluate_data_quality_gates`, `evaluate_source_scope_compliance`, the V25 count readers,
  `load_phase_07d_contract`. Table inventory stays **120** (no new table).

## OneDrive source-scope safe counts (the prompt requirement)

`source_scope_safe_counts(sources)` derives — **counts only, never folder names / paths / web URLs /
drive IDs / item IDs** — from `evaluate_source_scope_compliance` `sources[]`:
`onedrive_explicit_subset_sources` (scope_type selected_folders),
`onedrive_explicit_all_folders_sources` (scope_type all_folders_explicit),
`onedrive_implicit_root_blocked_sources` (onedrive + non_compliant),
`sharepoint_approved_all_nested_sources` (sharepoint + compliant). **Explicit all-folders selection
is counted as compliant, never misclassified as blocked** (live: all_folders=4, implicit_blocked=0).

## Static + test validation (exit codes)

| Command | Result |
|---|---|
| `python -m compileall src tests` | exit 0 |
| `ruff check .` | exit 0 — All checks passed |
| `mypy src` | exit 0 — no issues in **190** source files |
| `pytest -m "not live and not integration and not manual"` | **2221 passed**, 1 deselected (exit 0) |

(Prompt 11 baseline 2213; +8 new tests. Existing gate / contract / table-inventory tests unchanged.)

## CLI validation matrix (all exit 0)

`data-quality phase-07d-gates`, `data-quality {gates, no-writeback-proof, table-inventory}`,
`construction-agent validate`, `procore validate`, `graph files status/no-writeback-proof`,
`graph calendar status`, `graph mail status` — captured to `/tmp/p12/*.json` (ephemeral, not committed).

### Live `data-quality phase-07d-gates`

- `ok=true`, 12 gates, `required_fields_covered=true`, `phase_07d_intelligence_ready=true`,
  `review_required_total=0`. All twelve fields `pass` on the populated live DB.
- `source_scope_safe_counts` = {onedrive_explicit_subset 0, onedrive_explicit_all_folders 4,
  onedrive_implicit_root_blocked 0, sharepoint_approved_all_nested 10}.
- `no_writeback_proof` = {proof_passed true, guard_violations 0, pattern_hits 0, tables_scanned 10}.
- `data-quality gates` `meeting_prep_prerequisite_status` carries the same four safe counts.

### Safety invariants

- No-raw-content regex over the serialized `phase-07d-gates` + `gates` payloads → **no match**; no
  `folder_item_id` / raw path / URL / drive-or-item ID present.
- `data-quality no-writeback-proof` `proof_passed=true`; the 07D-scoped proof passes over all 10 V25
  tables; `graph files no-writeback-proof` `ok=true`.
- `table-inventory` `schema_version=25`, `contract_table_count=120` (no new tables).
- `data-quality gates` `meeting_prep_readiness_claim="ready"` — unchanged.

## Test-path coverage (new file)

full twelve-field report (coverage gates pass when seeded); empty DB defers coverage (never overstated
as pass) while the no-writeback proof still passes; review-required (a misrouted sensitive candidate →
routing gate fail_blocking + review_required_total≥1 + ok false); no-writeback proof clean + no-raw;
source-scope safe counts (monkeypatched registry: explicit all-folders not blocked; no folder/path/url/
id in output); idempotency; the `gates` command carries the safe counts; table inventory stays 120.

## Guardrails honored / stop conditions

- No external writeback / write scopes; the evaluator persists nothing (read-only).
- No raw content / folder names / paths / URLs / drive-IDs / item-IDs / token / secret in the report
  (no-raw + folder-id tests + both no-writeback proofs).
- Weak/model/sensitive never auto-promoted (routing gate fails on a misrouted sensitive candidate).
- Advisory only; readiness not overstated — coverage gates defer (not pass) on empty data.
- No stop condition triggered; all validations classified and passing.

## Handoff

- **Changed:** new `phase_07d.py` evaluator, `gates.py` safe-count helper + gate refinement,
  `__init__` export, `phase-07d-gates` CLI command, additive contract field list, new test file,
  `docs/architecture/55-…md`, this evidence, README 07D ledger.
- **Gates pass/fail:** live — all twelve 07D fields **pass**, intelligence-ready; on empty data the
  coverage gates **defer** (honest). `meeting_prep_readiness_claim="ready"` unchanged.
- **Next prompt allowed to proceed:** yes. Prompt 13 (the 07D no-writeback proof command
  `phase-07d-no-writeback-proof`, per the validation matrix) may surface the 07D-scoped proof as a
  standalone fail-closed command; the proof logic is already in place here.
