# Phase 08A — Data Quality Gates Proof (Prompt 14)

A read-only gate evaluator (`second-brain data-quality phase-08a-gates`) that aggregates the
existing per-surface validators + proofs into one pass/warning/fail/deferred conformance
report, **without overstating readiness**. Mirrors the established
`construction/data_quality/phase_07d.py` shape + status vocabulary
(`pass` / `warning` / `fail_blocking` / `deferred_not_blocking`).

## Repo-truth preflight

| Check | Result |
| --- | --- |
| `git rev-parse HEAD` (pre-commit) | `779f645` (Prompt 13) |
| Package-cited baseline | `c2656e1c` — does **not** match local repo; repo truth governs |
| `schema_version` | 26 (unchanged — no migration) |
| `contract_table_count` | 141 (unchanged) |
| Persistence | none — the gate report is computed read-only (matches the 07d gates posture) |

## Files changed

Created:
- `construction/second_brain/data_quality.py` — gate evaluator + proof
- `resources/json/phase_08a_data_quality_gates.json` — gates contract
- `tests/test_phase_08a_data_quality_gates.py`
- `docs/architecture/70-phase-08a-data-quality-gates.md`
- evidence: `phase-08a-gates-proof.json`, this file

Modified:
- `cli/second_brain.py` — `data-quality phase-08a-gates` subgroup + command
- `construction/second_brain/contracts.py` — register `data_quality_gates_contract`
- `construction/second_brain/__init__.py` — re-exports
- `tests/test_phase_08a_contracts.py` — `data_quality_gates_contract` in `_REQUIRED_KEYS`

## Validation commands and results

| Command | Result |
| --- | --- |
| `python -m compileall -q src tests` | exit 0 |
| `ruff check .` | All checks passed |
| `mypy src` | Success: 241 source files (benign pre-existing unused-override note) |
| `pytest tests/test_phase_08a_data_quality_gates.py tests/test_phase_08a_contracts.py` | all passed |
| `pytest -m "not live and not integration and not manual"` | exit 0 (full suite green) |
| `construction-agent validate --json` | `{total:4, passed:4, ok:true}` |
| `data-quality table-inventory --json` | `schema_version=26`, `contract_table_count=141` (unchanged) |
| `data-quality no-writeback-proof --json` | `proof_passed=true` |
| `second-brain data-quality phase-08a-gates --json` | exit 0; `ok=true` |

## Evidence proof

`phase-08a-gates-proof.json` → `proof_passed: true` (proof `phase_08a_data_quality_gates`):
- 12 gates; `status_counts = {pass: 8, warning: 1, fail_blocking: 0, deferred_not_blocking: 3}`.
- The four statuses are all representable (`gates_distinguish_pass_warning_fail_deferred=true`).
- `required_fields_covered=true` — gate names match the contract `required_fields` exactly.
- `no_readiness_overstatement=true`: offline/mock synthesis → `synthesis_liveness=warning`
  (runtime ready but synthesis not live), and the unimplemented surfaces
  (`mcp_exposure`, `model_call_receipt_persistence` (V27), `automation_hardening` (08B)) are
  `deferred_not_blocking` — never `pass`.
- `no_raw_content=true`.

### Gate set

| Gate | Status (healthy repo) | Source |
| --- | --- | --- |
| runtime_readiness | pass | config + schema == V26 |
| agent_registry | pass | registry + tool-policy proofs |
| model_profile | pass | model-profile proof |
| retrieval | pass | retrieval-broker proof |
| research_packet | pass | research-packet proof |
| evaluation | pass | output-evaluation (A05) proof |
| memory_provenance | pass | memory-curator proof |
| daily_brief_handoff | pass | delivery-handoff proof |
| synthesis_liveness | warning | offline/mock synthesis (no overstatement) |
| mcp_exposure | deferred_not_blocking | not implemented (08D) |
| model_call_receipt_persistence | deferred_not_blocking | V27 |
| automation_hardening | deferred_not_blocking | Phase 08B |

## Guardrail proof points

- **Distinguishes pass/warning/fail/deferred**: status vocabulary +
  `status_counts`; `fail_blocking` marks the report `ok=false` (exit 3) — none in a healthy repo.
- **No readiness overstatement**: mock/offline synthesis is a warning, unimplemented surfaces
  are deferred; `readiness_overstated=false`.
- **Read-only / no persistence**: the report is computed on demand; no table, no writeback.
- **No raw content**: report is metadata/status only; scanned for forbidden tokens.

## Reconciliations / known limitations

- No new schema/table; the gate report is not persisted (matches the 07d gates posture).
- The legacy `construction-agent data-quality` surface is unchanged.
- A `fail_blocking` only arises if an underlying proof/validator fails; in the current repo
  state none do (`ok=true`).

## Next prompt readiness

- Schema final at V26 / 141 tables; Prompt 06–13 proofs unchanged.
- The gate report gives a single readiness pane the validation matrix / no-writeback proof
  arm (later prompts) can build on.
