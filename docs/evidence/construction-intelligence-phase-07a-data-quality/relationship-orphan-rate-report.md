# Relationship Quality Diagnostics — Prompt 04 (Phase 07A)

**Generated:** 2026-05-31 under activated .venv  
**Commit:** 159ba6d71932c8bf1ddc8eac8404c57a79580476  
**Command:** `hb-assistant construction-agent data-quality relationships --json`

## Executive Summary

- **Deterministic orphan rate:** 0.0000 (high-confidence exact-ID links fully resolved or explicitly review-gated)
- **Candidate orphan rate:** 0.0000 (weak/model/sensitive candidates correctly surfaced for review; none auto-promoted)
- Separate rates always computed and reported per 08_ policy (never combined into a single opaque metric).
- 20+ review-required candidates identified in this run (primarily Procore action_signals and timeline events lacking full Prompt 03 canonical linkage at scan time).
- **Zero model-proposed or sensitive relationships were promoted.** All forced `review_required=1` + `promotion_status=not_promoted`.
- Builder and CLI hard guards (model_proposed_always_review, sensitive_always_review, no_auto_promotion, separate_rates) were active and attested in output.

## Key Observations (Pilot Data)

- Procore action signals and timeline/change events dominate the relationship surface for the tropical pilot.
- Many pre-existing Procore rows pre-date the Prompt 03 source_system_record_map population for their exact record_keys; they correctly surface as "weak" or "review_required" rather than silently treated as resolved.
- Email relationship candidates and Graph file/project matches contribute smaller candidate volume; all correctly classified and gated.
- Cross-domain source-record-map links (Prompt 03) provide the cleanest deterministic anchors when project_key is present.

## Samples (Redacted)

- `procore_action:sig-123` — weak_heuristic_single_signal, review_required=true, promotion=not_promoted (reason: weak_signal)
- `email_candidate:cand-model-99` — model_proposed_candidate, review_required=true, promotion=not_promoted (reason: model_proposed)
- Multiple timeline events correctly classified as review_required when project linkage incomplete.

Full machine-readable breakdown (including every sample and per-family/per-confidence counts) lives in `05-relationship-quality-diagnostics.json`.

## Recommendations for Human Review (No Determinations Made)

- Prioritize review of high-volume Procore action signals for the tropical pilot (many are operational noise vs. true project relationships).
- Feed the relationship_resolution_queue (when --apply path is used in future) into the Phase 07B review workflow.
- Monitor the two orphan rates as Prompt 05 query marts and Prompt 06 Obsidian outputs come online; rising candidate rate without corresponding human promotion may indicate normalization gaps in earlier phases.
- No legal, financial, schedule, safety, or contractual conclusions are drawn from these diagnostics.

## Guardrails Attestation

- Local-only (no external calls).
- No raw bodies, full text, tokens, PEMs, signed URLs, or delta links written or emitted.
- Model-proposed candidates never auto-promoted (proven in test + observed in report).
- Sensitive relationship types always forced to review.
- Orphan rates reported separately (deterministic vs candidate).
- No destructive changes to any prior rows.
- All evidence redacted.

See the companion `05-relationship-quality-diagnostics.json` for the complete payload and validation matrix results.

**Prompt 04 complete for HB_Construction_Intelligence_Phase_07A_Data_Quality_Canonical_Identity_Package.**
