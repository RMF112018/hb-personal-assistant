Repository: `RMF112018/hb-personal-assistant`  
Local path: `/Users/bobbyfetting/hb-personal-assistant`  
Branch: `experiment/phase-10-top3-local-model-agent-convergence`  
Evidence root: `docs/evidence/phase-10-top3-local-model-agent-convergence`

Hard constraints apply from `../README.md`, `../STOP_CONDITIONS.md`, and `../reference/02_SAFETY_CONTRACT.md`.

# Prompt 12 — Docs, Runbooks, and Architecture

## Objective

Update docs so the implemented behavior is understandable and no old docs overstate stale behavior.

## Required docs

Create/update:

- `docs/architecture/<next>-phase-10-top3-local-model-agent-convergence.md`
- `docs/runbooks/phase-10-top3-local-model-agent-convergence-runbook.md`
- README ledger if repo convention requires Phase 10 addendum entries
- relevant CLI help references
- evidence index

## Architecture note must cover

- three-candidate convergence
- Model Enriched Intelligence contract
- default-on behavior
- local-only model routing
- scheduler posture
- V45 raw enrichment productionization
- DB copy proof
- safety boundaries
- non-goals
- residual limitations, if any

## Runbook must cover

- manual daily-run dry-run
- manual daily-run apply on DB copy
- scheduler install preview
- scheduler status
- scheduler install apply, if Bobby chooses
- email raw enrichment readiness
- disabling Model Enriched Intelligence
- disabling email raw enrichment
- reading latest status
- locating latest browser brief
- interpreting degraded/withheld status
- rollback/uninstall scheduler steps
- emergency disable steps

## Evidence

Update:

- `24-known-limitations.md`
- `25-final-handoff.md` draft
