# Prompt 03 — Local Model Route and Structured Output

## Objective

Add the local-only model route and structured JSON contract for `email_followup_raw_enrichment`.

## Scope

Implement:

- New local model task family: `email_followup_raw_enrichment`.
- Config seed route in existing local model task routing files.
- Structured output schema / typed response model.
- Prompt template that accepts only sanitized bounded raw windows and deterministic candidate/watch metadata.
- Schema validation and repair using existing structured output framework.
- Tests for route, schema, no-cloud fallback, and validation failures.

## Model Routing Requirements

- Use local-only routing.
- Do not add cloud provider support.
- Do not allow cloud fallback.
- Prefer existing proven profile such as `mistral-nemo:12b` unless local eval evidence supports a different default.
- Heavy profiles may be optional/evaluation-only, not default.
- Fail closed when no local model is available.

## Structured Output Fields

The model output must be strict JSON equivalent to:

```json
{
  "enriched_title": "string",
  "waiting_state": "waiting_on_me|waiting_on_others|open|possibly_resolved|closed|unknown",
  "assignee_type": "me|other|mixed|unknown",
  "assignee_display": "string",
  "suggested_next_action": "string",
  "due_at_utc": "string|null",
  "confidence": 0.0,
  "reason_codes": ["string"],
  "cited_source_aliases": ["string"],
  "cited_candidate_ids": ["string"],
  "cited_watch_item_ids": ["string"],
  "raw_excerpt_hash": "string"
}
```

If repo conventions use different names, adapt, but preserve semantics.

## Validation Rules

Reject or withhold output when:

- JSON is invalid and cannot be repaired.
- Required fields are missing.
- `waiting_state` is outside allowed values.
- confidence is out of range.
- cited source aliases were not provided in the input.
- cited candidate/watch IDs were not provided in the input.
- `raw_excerpt_hash` does not match the input hash.
- suggested action contains raw excerpt text, URL, token, or HTML.
- output appears to invent a deadline not supported by provided context.

## Prompt Requirements

The prompt must instruct the model:

- Use only provided context.
- Do not infer commitments without evidence.
- Do not quote raw email text.
- Do not output URLs, tokens, email addresses, or raw excerpts.
- Prefer `unknown` or low confidence when ambiguous.
- Cite only provided source aliases and candidate/watch IDs.
- Distinguish deterministic candidate fields from model-enriched fields.

## Required Tests

Add tests for:

- Route exists.
- Route is local-only.
- Route has no cloud fallback.
- Structured schema accepts valid JSON.
- Structured schema rejects invalid enum values.
- Unknown source alias rejected.
- Unknown candidate/watch ID rejected.
- Hash mismatch rejected.
- Raw leakage in model output rejected.
- Model unavailable returns controlled degraded result.

## Stop Conditions

Stop if:

- Existing routing framework cannot add a local-only task family cleanly.
- Structured output framework would persist raw prompts/responses.
- Route would require a cloud model.

## Commit

After tests pass:

```bash
git add <routing config> <local_ai files> <tests>
git commit -m "feat(local-ai): add email follow-up raw enrichment route and contracts"
```

## Exit Criteria

- New task family implemented.
- Strict structured output validation implemented.
- No cloud fallback possible.
- Tests pass.
- Commit created.
