# 01 — Simplified architecture

Authoritative contract: **`docs/architecture/253-daily-brief-simplified-generation-contract.md`**.

Summary:

> **New Today is the daily brief. Candidate-derived sections, LLM synthesis, and Model Enriched
> Intelligence are diagnostics.**

- **One primary pipeline:** source changes → New Today business events → product status gate → shared
  render model → Markdown + HTML → collapsed diagnostics → status JSON.
- **One shared render model:** `new_today_presentation.build_render_model` feeds both surfaces.
- **One product status:** additive `daily_brief` block (`primary_surface=new_today`) drives the
  user-facing banner/warning; legacy top-level `status` preserved unchanged for backward compat.
- **Product-degradation-only gate:** `new_today_usefulness.evaluate_new_today_status` flips `degraded`
  only for email-followup-degraded, projection-degraded/coverage-degraded, or all-events-dropped;
  legacy synthesis/MEI/Ollama-unavailability never flip it and never warn above the fold.
- **Two distinct enrichment fields:** `new_today.model_enrichment_status` (New Today's own overlay) vs
  `diagnostics.model_enriched_intelligence_status` (legacy MEI). `--model-enriched-intelligence` is
  legacy-only.
