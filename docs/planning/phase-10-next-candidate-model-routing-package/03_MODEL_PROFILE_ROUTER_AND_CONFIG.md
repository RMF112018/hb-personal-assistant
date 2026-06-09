# 03 — Model Profile Router and Config

## Objective

Implement a local model profile registry/router that chooses the correct local model/profile per task, with deterministic fallback and no cloud LLM path.

## Scope boundaries

- Add routing config and router code.
- Do not alter all agents at once.
- Do not make daily-run depend on model availability unless fallback is deterministic and safe.
- No cloud route.

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

Add a config resource such as:

- `resources/config/local_model_profiles.seed.yaml`
- or equivalent repo-standard config path.

Profiles should include:
- profile id.
- model name.
- task families supported.
- temperature.
- context size.
- max output.
- JSON/schema mode.
- timeout.
- fallback profile.
- enabled flag.
- safety flags: local_only, no_cloud, no_raw_persistence.

Add router module such as:
- `src/hb_assistant/local_ai/model_router.py`

Required behavior:
- `select_model_profile(task_family, constraints)` returns a deterministic profile.
- Validates installed model availability.
- Emits blockers instead of silently selecting unavailable models.
- Provides fallback chain.
- Fails closed if no approved local model is available.
- Does not make network calls beyond local Ollama endpoint or existing local model client.
- Never falls back to cloud.
- Keeps existing hardcoded default behavior backward-compatible until integration steps switch consumers.

## CLI surface

Add or extend:

```bash
hb-assistant second-brain local-model profiles --json
hb-assistant second-brain local-model route --task-family daily_brief_synthesis_quality --json
hb-assistant second-brain local-model eval --models auto --json
```

Use repo conventions if command naming differs.

## Required tests

- Profile config loads.
- Invalid config fails closed.
- Unknown task family fails closed.
- Missing model produces blocker.
- Fallback chain works.
- No cloud route exists.
- CLI JSON shape is stable.

## Live validation required

```bash
.venv/bin/hb-assistant second-brain local-model status --json
.venv/bin/hb-assistant second-brain local-model profiles --json
.venv/bin/hb-assistant second-brain local-model route --task-family daily_brief_synthesis_quality --json
```

## Evidence required

- Config status.
- Model availability.
- Route result for each task family.
- Blocker behavior for a deliberately missing model.
- No raw data.

## Stop conditions

- Router requires credentials/auth changes.
- Router adds a cloud fallback.
- Router makes existing extraction/daily-run unstable.

## Commit behavior

Commit required:

```bash
git add ...
git commit -m "feat(local-ai): add local model profile router"
```

## Final response format

Return:
- Profile IDs.
- Supported task families.
- CLI results.
- Tests run.
- Guardrails.
