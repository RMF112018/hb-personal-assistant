You are working in Bobby's local repository:

`/Users/bobbyfetting/hb-personal-assistant`

Execute the objective defined at:

`/Users/bobbyfetting/hb-personal-assistant/docs/planning/phase-10-top3-local-model-agent-convergence-package/README.md`

Implement all three top candidates in one complete run:

1. Daily Brief Intelligence / Synthesis Convergence
2. Scheduler / Daily-Run Live Hardening
3. Email Follow-Up Raw Enrichment Productionization

Use the package README and every chained prompt in numeric order. Do not modify `main` directly. Do not merge, rebase, or use cloud LLMs. Do not mutate production DB during validation; use DB copies. Do not perform email, calendar, Procore, Graph, MCP, or external writeback. Stop on raw/private leakage, uncapped apply behavior, production DB mutation, cloud fallback, failed safety scan, or any evidence containing unsafe content.

Required product decisions:
- Model Enriched Intelligence is default-on.
- The rendered label is exactly `Model Enriched Intelligence`.
- Browser output must not auto-open.
- Scheduled apply runs may apply bounded local-only candidates only under conservative caps and explicit installed schedule behavior.

When complete, provide the final handoff using:

`docs/planning/phase-10-top3-local-model-agent-convergence-package/templates/FINAL_HANDOFF_TEMPLATE.md`
