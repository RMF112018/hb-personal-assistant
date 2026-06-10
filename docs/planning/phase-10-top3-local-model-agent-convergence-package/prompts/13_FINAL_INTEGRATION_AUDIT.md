Repository: `RMF112018/hb-personal-assistant`  
Local path: `/Users/bobbyfetting/hb-personal-assistant`  
Branch: `experiment/phase-10-top3-local-model-agent-convergence`  
Evidence root: `docs/evidence/phase-10-top3-local-model-agent-convergence`

Hard constraints apply from `../README.md`, `../STOP_CONDITIONS.md`, and `../reference/02_SAFETY_CONTRACT.md`.

# Prompt 13 — Final Integration Audit

## Objective

Conduct a fresh repo-truth audit of the completed branch before handoff.

## Required checks

Run:

```bash
git status --short --untracked-files=all
git log --oneline --decorate -20
git diff --stat main...HEAD
git diff --name-only main...HEAD
```

Audit:

- all changed files are in scope
- no secrets/private/raw content in changed files
- no generated unsafe outputs inside repo
- no `config/config.yml` tracked
- no cloud LLM route added
- no writeback path added
- no production DB mutation
- no raw prompt/response persistence
- no raw body persistence
- no uncapped apply
- all evidence files present
- all tests pass or failures are proven pre-existing
- docs/runbook updated
- final operator surfaces exist
- no TODO/FIXME/residual markers remain for package scope

## Required evidence

Create:

- `24-known-limitations.md`
- `25-final-handoff.md`
- update `21-validation-results.md`
- update `17-forbidden-string-scan.txt`

## Stop condition

If any package objective is incomplete, either finish it or document the exact stop condition. Do not call the package complete with unimplemented work.
