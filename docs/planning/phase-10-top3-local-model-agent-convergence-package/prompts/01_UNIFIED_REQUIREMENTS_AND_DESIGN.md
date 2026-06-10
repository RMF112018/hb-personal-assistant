Repository: `RMF112018/hb-personal-assistant`  
Local path: `/Users/bobbyfetting/hb-personal-assistant`  
Branch: `experiment/phase-10-top3-local-model-agent-convergence`  
Evidence root: `docs/evidence/phase-10-top3-local-model-agent-convergence`

Hard constraints apply from `../README.md`, `../STOP_CONDITIONS.md`, and `../reference/02_SAFETY_CONTRACT.md`.

# Prompt 01 — Unified Requirements and Design Lock

## Objective

Produce the detailed implementation design before changing behavior.

## Required audit

Inspect the live repo paths for:

- `daily_brief_intelligence.py`
- `daily_brief_llm_synthesis.py`
- `daily_run.py`
- `daily_run_html.py`
- `daily_run_scheduler.py`
- `pipeline.py`
- `email_followup_enrichment.py`
- `email_followup_pending.py`
- `raw_followup_window.py`
- `model_router.py`
- `resources/config/local_model_task_routing.seed.yaml`
- `resources/config/phase_10_local_model_profiles.seed.yaml`
- `cli/second_brain.py`
- relevant tests

## Required design decisions

Implement a single design contract with:

1. Final section label: **Model Enriched Intelligence**.
2. Default-on behavior for daily-run and scheduler.
3. Explicit disable flag.
4. Unified status JSON shape.
5. Browser/Obsidian rendering contract.
6. Email pending-enrichment integration contract.
7. Local model route/fallback contract.
8. Model-unavailable behavior.
9. Raw/private content boundary.
10. Validation and evidence plan.

## Required output

Create `04-unified-design-contract.md` with:

- final data-flow diagram in text
- affected modules
- CLI changes
- test plan
- evidence plan
- non-goals
- stop conditions

## Do not

- Do not implement code in this prompt.
- Do not change schema unless the audit proves there is no safe alternative.
