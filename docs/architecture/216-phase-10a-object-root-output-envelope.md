# 216. Phase 10A — Object-root model output envelope for live extraction

Date: 2026-06-08

Package: HB Construction Intelligence — Phase 10 / 10A Local Action Intelligence (repo-truth update)

## Context

The live extraction path reaches Ollama, but Ollama JSON mode always returns an **object** root even
when prompted for an array. Phase 10A's system/prompt asked for a JSON *array*, and the parser collapsed
any object lacking a usable list to `[]` — so `{"candidates": []}` (valid empty) and `{}` (malformed)
were both mis-reported as `empty_model_output`, and valid object-root candidate output was dropped. This
moves the action-extraction output envelope to object-root, keeps raw-array backward compatibility, and
makes diagnostics distinguish the real outcomes. All changes are in
`construction/second_brain/local_ai/raw_action_intelligence.py` + its tests (no schema/migration change).

## Decision

### Output envelope → object-root (`{"candidates": [...]}`)
- `STRICT_ACTION_SYSTEM` now instructs the model to output ONE JSON object with a top-level
  `candidates` array; for no actions, exactly `{"candidates":[]}`.
- `_build_prompt` emits object-root instructions + a compact valid example using current
  `ActionCandidate` enum values (placeholder `source_refs`/content only).
- `_run_with_retry_repair` and the outer-loop parse/envelope repair both say "Return ONLY a JSON object
  with top-level key `candidates` containing an array."

### Parsing — explicit key detection (backward compatible)
`json.loads(raw)` then: list root → use as-is (raw-array back-compat); object root with a `candidates`
(or `items`) **list** → use it (empty list allowed); object root without a usable list → **invalid
envelope** (retry with repair, never silently `[]`). A `parse_meta` block records `root_type`,
`has_candidates_key`, `has_items_key`, `response_char_count`, `parsed_candidate_count`.

### Diagnostics reasons
`_diagnostic_reason` precedence: `no_client_constructed` → `model_timeout` → `ollama_unreachable` →
`schema_rejected_output` → **`no_candidates`** (valid envelope, zero candidates) →
**`invalid_output_envelope`** (object without candidates/items) → `invalid_json_output` →
`empty_model_output` (truly empty/None raw output). `_build_diagnostics` adds the `parse_meta` fields.
Diagnostics carry only counts/booleans/type names — no raw response body, prompt, URL, token, email
body/subject, or source content.

## Verified behavior (mock)

| Mock output | produced | reason |
| --- | --- | --- |
| `{"candidates":[<valid>]}` | 1 | (accepted) |
| `{"candidates":[]}` | 0 | `no_candidates` |
| `[<valid>]` (array) | 1 | (accepted, back-compat) |
| `[]` | 0 | `no_candidates` |
| `{}` | 0 | `invalid_output_envelope` |
| `""` | 0 | `empty_model_output` |
| `{not json` | 0 | `invalid_json_output` |

## Guardrails / non-goals

No apply-path live persistence is enabled or recommended until a live dry-run returns accepted
candidates or explicit schema/business rejections. Dry-run default; diagnostics redacted. No migration,
no candidate-table change, no contract-JSON change (the single-candidate `phase_10_action_candidate_output_schema.json`
is unchanged — the array-vs-object envelope lives only in the extractor), no README/ledger bump.
