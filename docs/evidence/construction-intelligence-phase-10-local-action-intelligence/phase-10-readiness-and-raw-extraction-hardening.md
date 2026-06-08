# Phase 10 / 10A — Local Model Readiness + Raw Action Extraction Hardening (evidence)

Date: 2026-06-08 · Local-only · No external writeback · No raw-content leakage

## Acceptance criteria

| Criterion | Result | Evidence |
| --- | --- | --- |
| `local-model status` ready=true with `mistral-nemo:12b` installed | PASS | `build_local_model_status(provider_name="mock", mock_models={"mistral-nemo:12b",...})` → `ready=true`, `required_models=["mistral-nemo:12b"]`; regenerated `03-local-model-status-proof.{json,md}` |
| No status output suggests pulling qwen3 unless explicitly enabled | PASS | default `suggested_pull_commands` qwen3-free; `qwen3:30b` appears only with `--heavy-enabled` (heavy_context). The lone `qwen3` in 03 evidence is the explicit-enable-only heavy_context profile row, not a pull recommendation |
| Packet builders produce clean normalized text from `body_html` when `body_text` empty | PASS | `_normalized_body_text` + email/calendar end-to-end packet tests (`<p>Hello <b>world</b></p>` → `Hello world`, no tags) |
| `raw-action-candidates --dry-run` leaves task_candidates / commitment_candidates / candidate_source_refs / local_model_run_receipts unchanged | PASS | `test_dry_run_writes_nothing` — all four tables 0 rows; `persisted=0`, `would_persist=1` |
| `--apply` writes candidates only after schema + business-rule validation | PASS | apply path persists post-validation; generic/data-clean candidates rejected before persist |
| `candidate_source_refs.candidate_id` matches the persisted candidate `candidate_id` | PASS | `test_apply_persists_and_links_source_ref` — equality asserted; SHA-256-derived ids |
| New tests pass + targeted Phase 10 / 10A / MCP no-raw no-writeback tests | PASS | see Validation |

## Profile set (after change)

| profile_id | model | enabled | role |
| --- | --- | --- | --- |
| default_extract | mistral-nemo:12b | true | task/commitment/relationship extraction (required) |
| high_recall_extract | llama3.1:8b | true | high-recall bulk extraction |
| review_filter | qwen2.5:14b | true | secondary review / safety filter |
| quality_reasoning | gpt-oss:20b | false (explicit) | daily brief / MCP packet synthesis |
| heavy_context | qwen3:30b | false (heavy, explicit) | manual long-context synthesis |

`fast_extract` (qwen3:8b) removed; qwen3 disabled for structured extraction
(`structured_extraction_disabled_model_prefixes: ["qwen3"]`).

## Raw extraction correctness

- Dry-run is the default; zero writes at the source (no post-hoc count zeroing).
- `--source email|calendar|both` honored in packet and store-fallback paths.
- Deterministic SHA-256 stable keys → idempotent dedupe: re-apply over the same source refs yields one
  candidate row + one source-ref row (`test_deterministic_dedupe_on_reapply`).
- `candidate_source_refs.candidate_id` == persisted candidate id; 13 no-raw/no-writeback guard columns
  sum to 0; bounded `evidence_redacted` excerpts (≤400 chars) only — full raw stays in V42 tables.

## Validation

```
compileall src tests …………………………………… OK
ruff (changed/new files) ……………………………… clean
mypy (provider, raw_action_intelligence, raw_context) … Success
pytest (115) test_phase_10_local_model_readiness, test_phase_10a_raw_extraction_hardening,
  test_phase_10a_raw_action_intelligence, test_phase_10a_raw_model_context_packets,
  test_phase_10_contracts, test_phase_10_structured_output, test_phase_10_email_task_extraction,
  test_phase_10_ai_jobs, test_phase_10_fixture_runner, test_phase_10_schema,
  test_second_brain_no_writeback_proof ……… all pass
pytest MCP no-raw/no-writeback (phase_08d) … pass
second-brain local-model status --provider mock --json … required=mistral-nemo:12b, qwen3 pulls=[]
```

The `test_second_brain_no_writeback_proof` failures previously flagged on `provider.py: import requests`
are resolved by the urllib swap (proof_passed=true).

## Guardrails

Local-only; advisory; dry-run default. Not enabling email send, calendar mutation, Procore writeback,
cloud-LLM submission, or MCP raw exposure. No raw body/prompt/response/URL/token persistence.
