# 64 — Phase 08A: Retrieval Orchestrator (A01) + Research Packet Agent (A02) (Synthesized Prompt 07)

Status: implemented (Phase 08A Synthesized Prompt 07). Builds on records 57–63.
Deterministic, local-first, read-only, no-writeback, no new SQLite tables, no model.

## Purpose

Implements the **pre-synthesis context-quality gate**. The **Research Packet Agent
(A02)** assesses retrieved context — source coverage, stale/unknowns, conflicts,
review-tier density, accepted memory, open questions — and recommends graceful
degradation. The **Retrieval Orchestrator (A01)** routes a request, requires a research
packet for complex / daily-brief paths, and gates synthesis: **synthesis is allowed only
when a packet exists and context is not blocked; insufficient context degrades or blocks,
never overstates.** Substrate for Prompt 08 (interactive query / synthesis) and Prompt 13
(daily brief).

**No new tables** — V26 already ships `second_brain_research_packets` (+
`second_brain_evaluation_runs`, and `research_packet_id` on `retrieval_query_receipts` /
`daily_brief_runs`); schema stays **V26 / 141**. **No model / no embeddings / no
external access.**

## Repo-truth reconciliation (decisive)

- **Contract is repo-authoritative + compact.** The repo `research_packet_contract.json`
  (Prompt 02) defines V26-column-aligned `required_fields`, `context_quality_classes`
  (`sufficient/partial/insufficient`), and the **3-value** `degradation_modes`
  (`none/graceful_degraded/blocked`) — not the package's fuller proposed SQL
  (`packet_type`, `*_json` blobs, per-source tables). The persisted packet is the compact
  V26 receipt; the richer assessment (coverage detail, open questions, memory refs) is
  computed and **returned, not persisted raw**.
- **Two degradation vocabularies, mapped.** Retrieval/broker uses the 5-value
  `{none, narrow_claims, advisory_only, ask_for_targeted_research, blocked}`; the packet
  persists the 3-value via `_RECOMMENDATION_TO_PACKET_MODE` (narrow/advisory/ask →
  `graceful_degraded`). The 5-value actionable recommendation lives in
  `assessment.degradation_recommendation`.
- **Agents already registered** (A01 `second_brain_orchestrator_agent`, A02
  `research_packet_agent`); we implement their services, not the registry.
- **Out of scope:** Output Evaluation Agent (A05) + `second_brain_evaluation_runs`
  writes; interactive query / Claude synthesis (Prompt 08); daily brief generation
  (Prompt 13); memory curation (10–12). We build a `daily_brief` *packet* to prove the
  path — not the brief itself. No `migrator.py` / `safety.py` / contract-registry change.

## Seed

`resources/config/phase_08a_research_packet_policy.seed.yaml` — `required_for`,
`quality_thresholds` (tier-3 density 0.35, stale density 0.30, ref completeness 0.95,
repo-authored `min_source_coverage` 0.5), `degradation` map. Loaded deterministically
(no contract — like the context-budget seed).

## Code (`construction/second_brain/research/`, strict-mypy)

- `models.py` — `ResearchPacket` (compact, contract-aligned; persisted), 
  `ResearchPacketAssessment` (rich computed view; `accepted_memory_refs` rejects forbidden
  raw field names), `OrchestratorResult` (gating output).
- `policy.py` — `PACKET_TYPES`, `requires_research_packet`,
  `load_research_packet_policy_seed`, `score_context_quality` (deterministic precedence:
  empty/incomplete-refs → blocked; conflicts → ask_for_targeted_research; tier-3 density →
  advisory_only; stale density / low coverage → narrow_claims; else none),
  `validate_research_packet_policy`.
- `packet.py` (A02) — `build_research_packet` (reuses `RetrievalBroker` +
  `write_retrieval_receipt`; computes coverage vs the 7 reader-backed allowlisted
  families, tier distribution, stale/conflict, accepted-memory refs, redacted
  open-questions, policy warnings; assembles + optionally persists the packet),
  `build_research_packet_agent_proof`.
- `orchestrator.py` (A01) — `RetrievalOrchestrator.orchestrate`
  (`research_packet_ok = degradation_mode != "blocked"`; `synthesis_allowed` follows),
  `build_retrieval_orchestrator_proof`.
- `store.py` — `write_research_packet_receipt` (1:1 INSERT into
  `second_brain_research_packets`; guard CHECK columns 0; `coverage_warnings_json` holds
  warning codes; `review_status` `pending_review`), `read_latest_research_packets`.

Dry-run posture: `--no-emit-receipt` (default) performs **no** local DB writes (the
retrieval receipt is gated by `emit_receipt` too); `--emit-receipt` persists both the
linked retrieval receipt and the packet receipt.

## CLI

`hb-assistant second-brain research-packet build --packet-type <t> [--project-key]
[--emit-receipt/--no-emit-receipt]` → orchestrator gate; reports packet + assessment +
`research_packet_ok` + `synthesis_allowed` + degradation + warnings. Exit 0; 2 on invalid
`--packet-type`; 3 on build error.

## Guardrails

Local-first; external systems read-only; no Microsoft/Procore writeback; no raw content
emitted or persisted (RetrievalItem + assessment validators + contract guardrails);
research-packet + retrieval receipts metadata-only with CHECK(...=0) guard columns;
**synthesis requires a packet; insufficient context degrades/blocks, never overstates**.

## Evidence

`research-packet-agent-proof.json` + `retrieval-orchestrator-proof.json` (both
`proof_passed: true`); `07-retrieval-orchestrator-and-research-packet-proof.md`.
