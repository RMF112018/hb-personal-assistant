# 68 — Phase 08A Daily Brief Generation, Output Evaluation (A05) & Delivery Handoff

Status: implemented (Phase 08A Synthesized Prompt 12). Builds on records 57–67.

- Deterministic + mock-first; no model auto-selects live; metadata-only persistence;
  schema/contract-table count unchanged (V26 / 141). Apply writes approved Obsidian output
  only when gated; no macOS notification, no HTML rendering, no external delivery, no raw
  content.

## Purpose

Completes the `daily_brief_agent`: it generates the brief, runs the **Output Evaluation
Agent (A05)**, and **blocks apply unless evaluation passes** and the context is not blocked.
On apply it writes an approved, redacted, marker-bounded brief into the Obsidian vault; it
always emits a local-only, source-linked **Phase 08B delivery-handoff payload** carrying an
eligibility flag, a data-only notification summary, and HTML render-data. Generation is
mock-first through the Prompt-03 adapter's research-packet gate; the adapter result drives
evaluation + an in-memory model-call receipt only and is never written (live-mode
raw-response safety) — the written brief is rendered from the redacted cards (record 67).

## Repo-truth reconciliation (decisive)

- **No schema change.** `second_brain_evaluation_runs` already existed (V26) with no writer;
  this prompt adds the first writer (A05). `daily_brief_runs` already had `evaluation_run_id`
  + `output_path_redacted/hash`; the agent now populates them on apply. No delivery-handoff
  or notification table exists — the brief run *is* the delivery record; the handoff /
  notification / HTML structures are computed payloads. Schema stays V26 / 141 tables.
- **Contracts.** A05 reuses `evaluation_criteria_contract`; the `daily_brief_agent`
  `output_contract` is `agent_result` (no contract file). No new contract registered.
- **Apply output target.** Approved output is written to
  `<vault_root>/Work/HB Personal Assistant/12_Daily_Brief/<date>_daily_brief.md`
  (`PathPolicy().get_vault_root()`), marker-bounded (`HB-SECOND-BRAIN-DAILY-BRIEF`) + atomic.
  This is distinct from the legacy `obsidian/MarkerBoundedWriter` morning-run brief
  (`HB-DAILY-BRIEF` in Daily Notes) — they do not collide.
- **In-memory receipts.** Model-call / agent-run receipts remain V27-deferred (not persisted).

## Seed

`resources/config/phase_08a_daily_brief_policy.seed.yaml` gains (additive) an `apply_gate`
section (require_research_packet, require_evaluation_pass, min_evaluation_score,
block_apply_when_context_blocked) and a `delivery` section (local_only,
eligibility_requires_evaluation_pass, external_delivery_performed=false,
emit_macos_notification=false, render_html=false).

## Code

- `synthesis/store.py` — `write_evaluation_run(...)` → `second_brain_evaluation_runs`
  (checklist + counts + score + passed + tier/degradation; guard columns 0; row
  `review_status='pending_review'`, never the adapter's review_status whose vocabulary
  differs). `read_latest_evaluation_runs`. `synthesis/evaluation.py` adds
  `build_output_evaluation_agent_proof`.
- `daily_brief/context.py` — extracted `_assemble_daily_brief` (returns context + packet +
  assessment + envelope without persisting the brief run); `build_daily_brief_context`
  (Prompt 11 API) wraps it unchanged.
- `daily_brief/output.py` — `render_brief_markdown` (redacted, from cards) +
  `write_brief_output` (dry-run computes content + hash, writes nothing; apply atomically
  writes the marker-bounded section, preserving user text outside the markers) +
  `resolve_brief_path`.
- `daily_brief/generate.py` — `run_daily_brief(...)` orchestrates assemble → generate
  (mock-first) → evaluate (A05) → gate apply → write output → persist brief run (with
  `evaluation_run_id` + `output_path_*`) → build handoff; `build_daily_brief_agent_proof`
  + `build_daily_brief_delivery_handoff_proof`.
- `daily_brief/models.py` — `NotificationSummary` (`channel=local_only`, `emitted` forced
  False), `HtmlRenderingData` (`format=render_data`, `rendered` forced False),
  `DeliveryHandoffPayload` (`phase=08B`, `local_only` forced True,
  `external_delivery_performed` forced False), `DailyBriefResult`.
- `daily_brief/store.py` — `write_daily_brief_run` extended with optional
  `evaluation_run_id` / `output_path_redacted` / `output_path_hash` (Prompt 11 callers
  unaffected).

## CLI

`hb-assistant second-brain daily-brief generate --date YYYY-MM-DD [--project-key K]
[--mode dry_run|apply] [--emit-receipt] [--json]` — emits the evaluation summary, `applied`,
`apply_blocked_reason`, `eligible_for_delivery`, redacted output path, and the
delivery-handoff summary; exit 0 ok, 2 invalid mode, 3 failure. `daily-brief build` /
`triage` (Prompt 11) are unchanged.

## Guardrails

Mock-first generation; requires research packet; apply blocked unless evaluation passes and
status is not blocked. Vault write only on explicit apply (dry-run default; tests/proofs use
temp dirs). No raw prompts/responses/bodies/document text/calendar/URLs/secrets persisted
(output rendered from redacted cards, never the adapter answer). Handoff is local-only +
source-linked; notification + HTML are data-only and never emitted/rendered; no external
delivery. Metadata-only receipts with guard columns 0.

## Evidence

`docs/evidence/construction-intelligence-phase-08a-second-brain-runtime/`:
`output-evaluation-agent-proof.json`, `daily-brief-delivery-handoff-proof.json`
(`proof_passed: true`), `daily-brief-dry-run.md`, with the narrative in
`daily-brief-agent-proof.md`.
