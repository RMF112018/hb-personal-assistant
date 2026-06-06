# Daily Brief V2 — Repo-Truth Rebaseline (Prompt 00)

**Package:** HB_Construction_Intelligence_Phase_09_Addendum_Daily_Brief_V2_Executive_Utility_Hardening
**Prompt:** 00 — Repo-Truth Audit and Baseline
**Date:** 2026-06-06 · **Read-only audit; no code changes in this prompt.**

## Git Baseline

- Branch: `main` · HEAD: `76f515121478ce53a65699295d5c458aa9523979`
- `git pull --ff-only`: already up to date with `origin/main`.
- Working tree: pre-existing timestamp/sha churn across many `docs/evidence/**` files plus untracked `.claude/`, `.code-graph/`, `frontend/`, `package-lock.json`, `scripts/hb-claude-mcp-launcher.sh`, `docs/architecture/176-*.md`. None relate to Daily Brief V2.

## Implementation Surface (current V1)

| Concern | Location |
| --- | --- |
| Packet builder | `daily_brief/packet.py` → `build_daily_brief_packet()` (~L265-339); `RENDERING_INSTRUCTIONS` (~L40-62) |
| MCP handoff status | `daily_brief/mcp_handoff_status.py` → `build_daily_brief_mcp_handoff_status()` |
| Claude rendering template | `resources/templates/claude_daily_brief_{scheduled_task,manual_run}.md`; proof in `mcp/render_template_proof.py` |
| Deterministic render | `daily_brief/output.py` → `render_brief_markdown()` (~L92-168) |
| Rendered-brief proof | `daily_brief/rendered_quality.py` → `build_daily_brief_rendered_quality_proof()` |
| Output-receipt proof | `daily_brief/output_receipt.py` → `build_daily_brief_rendered_output_receipt_proof()` |
| CLI commands | `cli/second_brain.py` group `second-brain daily-brief`: build, packet, packet-proof, rendered-proof, output-receipt-proof, mcp-handoff-status, triage, generate, render-view, schedule-preview |
| Output path | `daily_brief/output.py` → `resolve_brief_path()`; `_VAULT_SUBDIR = "Construction Intelligence/Phase 08A Daily Briefs"` |
| Phase 09 handoff evidence | `docs/evidence/construction-intelligence-phase-09-daily-brief-mcp-handoff/` |

## Reproduced Behavior

- `packet --date 2026-06-06 --json` → `source_coverage=0.6`, `source_ref_count=363`, `project_count=1`, `review_required=0`, `stale=0`. `what_matters_today` = `["project:tropical items=12 (rev_exc=0, stale=0) [tier 1]"]`. `recent_changes` are cross-source relationship edges (e.g. `procore->procore_entity created_by [accepted_human_promoted]`).
- `packet-proof --json` → `proof_passed=true`; section_counts recent_changes=3, review_required=1, aging=1, meeting_prep=0, risk=1, stale=2, accepted_memory=1.
- `mcp-handoff-status --json` → `handoff_closeout_ok=true`; pass=4, deferred=1; `production_readiness=false`.
- `rendered-proof --json` → 10 checks; safe fixture passes, each tampered variant fails its expected check.
- `output-receipt-proof --json` → `import_enabled=false`; rendered narrative excluded from trusted stores.

## Documented Defects

1. **D1 — Provenance leaks into body.** Per-item `item_id`/`source_ref_hash`/`source_ref_label`/`blocked_uses`/`confidence_class`/`review_tier` surface as provenance, rendered inline rather than as plain activity.
2. **D2 — Guardrail/proof/internal commentary in body.** `output.py` L103-109 status banner (`degradation=…; review_tier=…; source_coverage=…; Tier-3 items routed to mandatory review`) and L146-150 "Batched/suppressed" governance block with CLI recommendations (`run hb-assistant second-brain review burden`) belong in proofs, not the brief.
3. **D3 — Source coverage dominates.** `source_coverage_summary` is the largest packet block; render leads with the coverage/degradation banner and appends Coverage Notes. Coverage should be a short confidence footnote.
4. **D4 — Count-only tables.** Project Signals render as `project X: N item(s), M review-required`; `what_matters_today` is `project:tropical items=12 (rev_exc=0, stale=0) [tier 1]` — counts, no descriptive detail.
5. **D5 — Relationship metadata instead of project activity.** `recent_changes` are `cross_source_relationships` edge labels, not human-readable descriptions of what happened on the project.
6. **D6 — Weak/missing agenda/deadline/focus.** No explicit "what happened yesterday", "today's agenda", "deadlines next 7 days", or "what to focus on". `meeting_prep` count was 0; no calendar agenda or deadline horizon. Template sections are governance-oriented.
7. **D7 — Output path is wrong.** `resolve_brief_path()` → `/Users/bobbyfetting/Documents/Obsidian Vault/Construction Intelligence/Phase 08A Daily Briefs/<date>_daily_brief.md`; `RENDERED_NARRATIVE_LOCATION` → `<vault>/Construction Intelligence/Phase 09 Rendered Daily Briefs/`.

## Correct Output Path (V2 target)

```
/Users/bobbyfetting/Documents/Obsidian Vault/Work/Daily Brief/
```

Current resolved path: `…/Obsidian Vault/Construction Intelligence/Phase 08A Daily Briefs/2026-06-06_daily_brief.md` — **must be migrated** in a later prompt.

## Acceptance Bar (for V2, per package)

A construction executive reads the brief in under 3 minutes and understands: what happened yesterday, today's agenda, deadlines in the next 7 days, what needs attention, and what to focus on — **without** reading packet/proof/governance internals.
