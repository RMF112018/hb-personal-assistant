# 08 — Docs, Evidence, and Runbook

## Objective

Document the local model evaluation + routing family and add an operator runbook for using it after the daily-run pilot is stable.

## Scope boundaries

- Documentation/evidence only unless tiny fixes are necessary.
- Do not overstate readiness.
- Do not include raw outputs.

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


## Documentation targets

Update or add:
- Architecture record: `docs/architecture/<next-number>-phase-10-local-model-routing.md`
- Evidence README: `docs/evidence/phase-10-local-model-routing/README.md`
- Runbook section: local model eval/routing and daily-brief intelligence.
- README phase ledger if repo convention requires it.
- Agent registry docs if a new agent entry is added.

## Required content

Architecture doc:
- Purpose.
- Data flow.
- Model profile/router design.
- Eval task families.
- Daily-brief intelligence integration.
- Guardrails.
- Fallback behavior.
- Non-goals.
- What is not implemented.

Evidence:
- Redacted command-output summary.
- Tests.
- DB-copy proof.
- No-writeback proof.
- No raw-prompt/response proof.
- Model metrics table.
- Known limitations.

Runbook:
- How to check installed models.
- How to run eval.
- How to view routing.
- How to run a daily brief with intelligence.
- How to disable intelligence.
- How to interpret failure/fallback.
- Where outputs are written.
- How to avoid committing raw local outputs.

## Validation required

- Review docs for raw tokens/URLs/emails.
- Run repo search for forbidden strings in evidence/docs.
- Confirm README does not claim production readiness unless proven.

## Stop conditions

- Evidence cannot be redacted without losing meaning.
- Docs would contradict repo truth.
- Runbook requires manual steps that are unsafe by default.

## Commit behavior

Commit required:

```bash
git add docs README.md resources/config || true
git commit -m "docs(local-ai): document model routing brief intelligence"
```

## Final response format

Return:
- Docs changed.
- Evidence folder.
- Runbook summary.
- Limitations.
