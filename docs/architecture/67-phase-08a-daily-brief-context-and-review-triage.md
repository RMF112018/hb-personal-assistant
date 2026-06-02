# 67 — Phase 08A Daily Brief Context Builder (daily_brief_agent) + Review Triage Agent (review_triage_agent)

Status: implemented (Phase 08A Synthesized Prompt 11). Builds on records 57–66.

- Deterministic, local-first, read-only; no model call; metadata-only persistence; schema/
  contract-table count unchanged (V26 / 141). External systems untouched; no HTML, no
  notifications, no source-system writeback.

## Purpose

Turns approved, source-linked context into the daily brief's **inputs** without rendering
or delivering anything. The Daily Brief Context Builder (`daily_brief_agent`) retrieves once
via the Retrieval Broker (record 61), assesses that envelope with the Research Packet Agent
(record 64), then deterministically groups items into five card kinds — attention items,
meetings, projects, warnings, review-required — and a structured **delivery handoff input**.
The Review Triage Agent (`review_triage_agent`) summarizes the **review load** grouped by
tier, source, project, and urgency. Insufficient context degrades or blocks; it never
overstates, and Tier-3 items are surfaced for mandatory review rather than treated as fact.

## Repo-truth reconciliation (decisive)

- **No schema change.** V26 already ships `daily_brief_runs` + `daily_brief_source_refs`
  (V24). The builder reuses them as-is; schema head stays V26 / 141 contract tables. The
  package-cited baseline `c2656e1c` does not match the local repo (`03bfadb`); repo truth
  governs (same posture as Prompts 06–10).
- **Contract authority.** A compact `daily_brief_contract` (required_fields, `brief_sections`,
  `card_kinds`, `delivery_handoff_fields`, guardrails) is registered and owned by this
  prompt. Triage reuses the existing `review_tier_contract` (its registry `output_contract`)
  rather than introducing a triage contract.
- **Triage is read-only.** No V26 triage table exists; `ReviewLoadStatus` is a computed
  summary (consistent with the `review_triage`/`status` tool groups). Daily-brief runs are
  the only persisted artifact, and only as metadata.
- **Degradation vocabulary.** The brief carries the packet's 3-value `degradation_mode`
  (`none`/`graceful_degraded`/`blocked`) and `context_quality_class`, reused unchanged.
- **Agents already registered.** `daily_brief_agent` and `review_triage_agent` were
  registered in the Prompt 02 addendum; this prompt implements their services.

## Seed

`resources/config/phase_08a_daily_brief_policy.seed.yaml`
(`phase_08a_daily_brief_policy_v1`): dry-run-first assembly; `render_html: false` /
`emit_notifications: false`; deterministic triage prioritization order
(`review_tier → urgency → source_family`); review-tier mapping; card-kind vocabulary.
Standalone deterministic config (the contract owns the section/card vocabulary).

## Code

`src/hb_assistant/construction/second_brain/daily_brief/`:

- `models.py` — `AttentionItemCard`, `MeetingCard`, `ProjectCard`, `WarningCard`,
  `ReviewRequiredCard` (Tier-3-only validator), `ReviewLoadStatus`, `HandoffLine`,
  `DeliveryHandoffInput` (`output_format` literal `structured_data`; rejects
  `notification_emitted=True`), `DailyBriefContext`. Field validators reject any forbidden
  raw reference field; `extra="forbid"` throughout.
- `policy.py` — `load_daily_brief_policy_seed`, `reason_code_for_tier`,
  `validate_daily_brief_policy` (+ `DailyBriefPolicyError`).
- `triage.py` — `build_review_load_status` + `ReviewTriageAgent.summarize` (broker-backed),
  deterministic urgency banding, `build_review_triage_agent_proof`.
- `context.py` — `build_daily_brief_context` (retrieve once → packet → cards → review load →
  handoff → optional persist), card/handoff builders, `build_daily_brief_context_builder_proof`.
- `store.py` — `write_daily_brief_run` (→ `daily_brief_runs` + `daily_brief_source_refs`,
  guard columns 0, `output_path_*` NULL) and `read_latest_daily_brief_runs`.

Dry-run is the default; `--no-emit-receipt` performs zero local writes.

## CLI

`hb-assistant second-brain daily-brief build --date YYYY-MM-DD [--project-key K]
[--mode dry_run|apply] [--emit-receipt] [--json]` — emits source coverage, review-tier
counts, per-kind card counts, review load, and the delivery-handoff summary; exit 0 ok,
2 invalid mode, 3 failure.

`hb-assistant second-brain daily-brief triage [--project-key K] [--json]` — emits the
review-load status; exit 0 ok, 3 failure.

## Guardrails

- Deterministic; external systems read-only; no source-system writeback; no model call.
- No HTML, no notifications (delivery handoff is structured data only; no output file).
- No raw bodies/document text/calendar payloads/prompts/responses/URLs/secrets persisted or
  logged; metadata-only receipts with guard columns 0.
- Synthesis-discipline reused: context comes from the broker + research packet; Tier-3 is
  surfaced for review, never concluded; insufficient context degrades or blocks.

## Evidence

`docs/evidence/construction-intelligence-phase-08a-second-brain-runtime/`:
`daily-brief-context-builder-proof.json` and `review-triage-agent-proof.json`
(`proof_passed: true`), with the narrative in
`11-daily-brief-context-and-review-triage-proof.md`.
