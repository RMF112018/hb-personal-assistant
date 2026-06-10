# 24 — Known Limitations (true residual limitations only)

1. **Two model calls remain by design.** The narrative synthesis (`synthesize_daily_brief`) and the
   advisory intelligence adapter (`build_daily_brief_intelligence`) are distinct local-model calls.
   Convergence is at the render/status contract layer (one **Model Enriched Intelligence** section),
   not by merging the upstream calls. This is intentional and operator-approved (lowest-risk reuse of
   two tested paths); a single-call rewrite is explicitly out of scope for this phase.

2. **Natural production eligibility is currently zero.** On the production-copy, no naturally-occurring
   email-source-linked accepted follow-up records were eligible for raw enrichment (`11` natural
   readiness). The readiness surface now makes this explicit and actionable; the persistence/cap/
   idempotency proofs (`12`–`14`) and the integrated run (`15`) use clearly-labeled seeded-copy
   fixtures. This is a data state, not a defect.

3. **MEI degradation does not downgrade the run to "partial".** Because the Model Enriched
   Intelligence section is advisory-only, a model-unavailable/withheld MEI leaves the run status as
   `success` (deterministic brief is authoritative) while reporting MEI `degraded/withheld` in status.
   The narrative synthesis path retains its own fail-closed → `partial` behavior, unchanged.

4. **Scheduler `install --apply` not exercised.** Per safety constraints, no real `launchctl` install
   was performed; only dry-run/plan preview + status were validated. The operator runs the documented
   `--apply` step at their discretion (runbook).

5. **Live end-to-end model output not captured in evidence.** All committed proofs use injected
   deterministic backends to stay raw-free and reproducible; real Ollama output is intentionally not
   persisted (no raw prompt/response in any artifact).

No other residual limitations are known for this package's scope.
