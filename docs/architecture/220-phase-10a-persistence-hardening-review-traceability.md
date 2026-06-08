# 220. Phase 10A — Persistence hardening (force review + traceability)

Date: 2026-06-08

Package: HB Construction Intelligence — Phase 10 / 10A Local Action Intelligence (repo-truth update)

## Context

Follow-up to ADR 219. Before any batch apply, every persisted Phase 10A candidate must be
human-review-gated and source-attributable. Today the model's `recommended_next_action` is persisted
as-is (a non-high-stakes `accept` would persist as `accept`), and `model_profile_id` /
`prompt_template_version` are persisted only when the model emits them — frequently null. This forces
`review` and populates traceability defaults at accept time. All changes are in
`construction/second_brain/local_ai/raw_action_intelligence.py` + tests (no schema/migration/contract).

## Decision

### Module defaults
```
DEFAULT_EXTRACT_PROFILE_ID = "default_extract"
PHASE10A_PROMPT_TEMPLATE_VERSION = "phase10a-action-extraction-v1.2.7"
```

### Normalize accepted candidates (one `model_copy`)
The existing post-alias-resolution `model_copy` in the accept loop of
`extract_action_candidates_from_raw` is extended so every accepted candidate is normalized BEFORE the
report/persist branches (dry-run report + apply persist alike):

- `recommended_next_action` → `"review"` for all live local-model candidates.
- `model_profile_id` → model value or `default_extract`.
- `prompt_template_version` → model value or `phase10a-action-extraction-v1.2.7`.
- `model_name` → model value, else `client.model`, else `"mock"` (mock-output path), else null.
- `input_window_hash` → model value, else first 12 hex of `sha256(prompt)`.

`model_copy` does not re-validate; `review` always satisfies the `ActionCandidate`
`_high_stakes_routing` validator. The persist `common` dict already reads
`cand.recommended_next_action` / `cand.model_profile_id` / `cand.prompt_template_version`, so persisted
`task_candidates` / `commitment_candidates` rows pick up `review` + non-null traceability with no
further change. V41 tables have `model_profile_id` + `prompt_template_version` columns but NO
`model_name` / `input_window_hash` columns, so those two are carried on the candidate dump
(reporting-only).

## Verified (mock, apply path)

- Object-root candidate citing `src_1` with model output `recommended_next_action=accept` (normal
  safety) → persisted row `recommended_next_action == "review"`.
- Model omits `model_profile_id` / `prompt_template_version` → persisted
  `default_extract` / `phase10a-action-extraction-v1.2.7` (non-null).
- Report candidate carries non-null `model_name` (`mock`) + `input_window_hash`.
- No-raw / no-writeback guard columns sum to 0 on `task_candidates` + `candidate_source_refs`.

## Guardrails / non-goals

Dry-run default; no live `--apply` here; no email/calendar/Procore/MCP-raw/cloud-LLM writeback. Source
aliases, object-root envelope, and no-raw/no-writeback proofs preserved. No schema/migration/contract
change, no README/ledger bump.
