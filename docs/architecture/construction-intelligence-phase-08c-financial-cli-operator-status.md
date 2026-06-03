# Phase 08C — Financial CLI and Operator Status

Design record for the operator-usable Phase 08C financial CLI surfaces. All commands are
read-only / local-first and advisory-only. Repo code, tests, and evidence are authoritative.

## Command catalog

All under `hb-assistant second-brain …`:

| Command | Builder | What it does |
| --- | --- | --- |
| `financial readiness` | `financial_completeness.run_financial_fact_readiness_agent` | Financial Fact Readiness Agent snapshot (V35) + proof |
| `financial coverage` | `financial_completeness.build_financial_source_coverage_matrix` / `build_source_coverage_snapshot` | Source coverage matrix + snapshot (6-status) |
| `financial exposure-summary` | `financial_completeness.build_financial_exposure_mart_preview` | Advisory exposure marts (deterministic vs candidate) |
| `financial review-items` | `financial_review_routing.build_financial_review_required_proof` | Route the 7 review-required signal categories (V35/V36) |
| `financial no-writeback-proof` | `financial_no_writeback.build_financial_no_writeback_proof` | Empirical no-writeback / no-raw / no-float attestation |
| `data-quality phase-08c-gates` | `data_quality.evaluate_phase_08c_data_quality_gates` | V35 financial data-quality gates |

Each is read-only externally: it may write local SQLite rows and evidence files under
`docs/evidence/construction-intelligence-phase-08c-financial-readiness/`, but performs no Procore /
Graph call and no external writeback. `readiness`, `review-items`, and `no-writeback-proof` call
`SQLiteMigrator().apply()` first.

## Operator envelope

Every command emits a consistent envelope so operators can rely on the same fields:

- `command`, `phase: "08C"`, `ok`
- `project_key` — the `--project` value (or `null`)
- `advisory_only: true`
- `guardrails` — `_08C_GUARDRAILS` (local_first, read_only, no_external_writeback,
  no_raw_financial_payload, financial_determination_forbidden, advisory_only)
- `attestations` — `_08C_ATTESTATIONS`, the explicit no-determination block:
  `financial_determination_performed / payment_decision_performed /
  claim_or_entitlement_decision_performed / external_writeback_performed /
  raw_financial_payload_persisted / live_procore_call_performed` all `false`
- `evidence_paths` — the proof/preview artifact paths the command produced or references
- a command-specific `summary`

Shared CLI helpers live next to the commands in `cli/second_brain.py`: `_08C_GUARDRAILS`,
`_08C_ATTESTATIONS`, and `_emit_08c(payload, *, json_out, human, exit_code)`.

## JSON vs human output

Mirroring `cli/procore.py`, each command takes `--json/--no-json` (JSON is the default). `--no-json`
prints a concise operator summary (key metrics + evidence path). `_emit_08c` raises `typer.Exit`
with the chosen exit code; `no-writeback-proof` exits `0` when the proof passes and `3` otherwise.

## No-writeback / no-raw proof checks

`build_financial_no_writeback_proof` (`construction/second_brain/financial_no_writeback.py`) is
deterministic and read-only, and proves the posture empirically:

- **guard_columns** — every V35 financial table carries the guard columns and zero rows violate
  `advisory_only=1` / all `*_persisted=0` / all `*_performed=0` (CHECK-pinned; the count proves it).
- **money_not_float** — no money column in the V35 or `procore_financial_*` tables is declared `REAL`;
  `amount_facts_normalized.canonical_decimal_text` is `TEXT` and `minor_units` is `INTEGER`.
- **evidence_redaction** — no JSON evidence artifact under the 08C evidence directory matches a
  forbidden raw pattern (tokens / PEM / JWT / URL / signed-url / bare email); findings record only
  `filename:rule_N`, never the matched text or the regex source. Hand-authored narrative `.md` docs
  are excluded (they legitimately describe the patterns); machine `.md` proofs are self-scanned by
  their own generators at write time.
- **no_live_no_writeback** — read-only local attestation; no Procore/Graph call, no external mutation.

`proof_passed` is the AND of all checks. The proof is written as
`financial-no-writeback-proof.md` (+ `.json`) and self-scanned for raw patterns before write.

## Files

- `src/hb_assistant/cli/second_brain.py` — `_08C_ATTESTATIONS`, `_emit_08c`, six commands.
- `src/hb_assistant/construction/second_brain/financial_no_writeback.py` — proof generator.
- `tests/test_second_brain_financial_cli.py` — CLI envelope (JSON + `--no-json`), exit codes.
- `tests/test_phase_08c_financial_no_writeback.py` — real generator (clean pass + raw-value fail).
