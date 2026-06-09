# 02 — Model Eval Harness and Fixture Contracts

## Objective

Implement a local-only model evaluation harness that can compare installed local models/profiles on the repo's actual structured-output tasks without raw data egress.

## Scope boundaries

- Add eval harness and safe fixture contracts.
- Do not integrate into daily brief yet.
- Do not mutate live DB.
- Do not persist raw prompts or raw responses.
- Evidence must be metrics-only/redacted.

Hard constraints:
- Do not modify `main`. Work only on the approved experiment branch for this package.
- Do not merge, rebase main, or imply a merge.
- No cloud LLM submission unless Bobby separately approves it.
- No automatic email send.
- No calendar mutation.
- No Procore writeback.
- No Graph writeback.
- No external writeback.
- No MCP raw exposure.
- No production DB mutation unless explicitly approved.
- No destructive migration unless explicitly approved.
- No credential/auth changes unless explicitly approved.
- No raw email/calendar/Procore/document body content committed to repo.
- No raw prompts, raw model responses, signed URLs, download URLs, join URLs, access tokens, refresh tokens, secrets, credential material, or unsafe HTML committed to repo, evidence, docs, tests, or logs.
- Raw local content may be used only for local operator consumption where explicitly allowed and must never be persisted to guarded candidate/evidence tables.
- Default persisted rows and repo evidence must remain redacted/guarded.
- Any apply/persist behavior must be capped, bounded, idempotent, source-linked, and review-safe.


## Implementation instructions

Implement a module such as:

- `src/hb_assistant/local_ai/model_eval.py`
- `src/hb_assistant/local_ai/model_eval_fixtures.py`
- `src/hb_assistant/local_ai/model_eval_metrics.py`

Use actual repo naming if different.

Required concepts:
- `ModelEvalTask`: task id, task family, schema name, prompt template id, fixture id, max context, expected shape.
- `ModelEvalFixture`: redacted/synthetic input, expected JSON schema, rubric expectations.
- `ModelEvalResult`: model, profile, fixture, duration, json_valid, schema_valid, redaction_passed, usefulness_score, error_code, no raw prompt/response.
- `ModelEvalSuite`: runs deterministic tasks across one or more installed local models.

Task families at minimum:
- email_action_extraction_json
- daily_brief_synthesis_quality
- calendar_prep_summary
- procore_digest_summary
- short_operator_catchup

Fixtures:
- Include synthetic fixtures in repo.
- Allow optional local-only fixture directory outside repo for raw operator samples.
- Raw fixture support must be opt-in and must refuse repo-contained paths.
- Repo fixtures must be redacted and safe to commit.

Metrics:
- JSON valid rate.
- Schema valid rate.
- Redaction scanner pass/fail.
- Latency.
- Token/context fit if available.
- Operator usefulness rubric score.
- Failure category.

## Required tests

Add tests for:
- Synthetic fixture loading.
- Refusal of repo-contained raw fixture paths.
- No raw prompt/response in persisted/returned evidence payloads.
- JSON/schema metric calculation.
- Redaction scanner catches URLs/emails/join links/tokens.
- Model client failure returns structured fail-closed result.

## Live validation required

Run on synthetic fixtures only:

```bash
.venv/bin/hb-assistant second-brain local-model eval --fixtures synthetic --models mistral-nemo:12b --json
```

Adjust command name if implementation chooses a different final surface.

## Evidence required

Capture:
- Command.
- Models attempted.
- Fixture counts.
- Metrics.
- No raw input/output.
- Redaction pass status.

## Stop conditions

- Eval harness requires cloud models.
- Eval harness must persist raw prompts/responses to work.
- Synthetic fixtures cannot exercise at least three task families.

## Commit behavior

Commit required if implementation succeeds:

```bash
git add ...
git commit -m "feat(local-ai): add local model evaluation harness"
```

## Final response format

Return:
- Files changed.
- CLI/eval surface added, if any.
- Tests run.
- Synthetic eval proof.
- Guardrail proof.
