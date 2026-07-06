# Risks + Deferred

Deferred (out of N8C-5 scope, no code):
- Live distributed MacBook/NAS worker deployment + daily Ollama launch (operator setup only).
- Local enrichment WRITE API (behind reserved default-OFF `HB_ASSISTANT_ENRICHMENT_WORKER_API`).
- Remote MCP enrichment tools of any kind.
- Autonomous curation, context packs, entity/concept/graph compiler, open-loop workflows, feedback
  learning, frontend command center, `claim_validation` job execution.

Risks / watch items:
- Shared worktree: N8C-5 was built alongside a concurrent N8D-1 (V102) session; a discard/restore
  wiped the V101 migrator wiring mid-build (re-applied + re-verified). N8D-1 now lives in a separate
  worktree; N8C commits first. If N8D-1 later stacks V102, its owner must bump LATEST_SCHEMA_VERSION
  to 102 and update the head-pin canary (`test_latest_schema_version_is_101`). N8C-5's own enrichment
  tests assert the V101 row (not the head number) so they survive later additive migrations.
- Live model output is untrusted: bounded + validated before storage; oversized/malformed fails with
  a receipt, never truncate-ingested; claims only ever candidate/unreviewed.
