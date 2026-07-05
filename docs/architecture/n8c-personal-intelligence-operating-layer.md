# N8C — Personal Intelligence Operating Layer

> Status: **contract / normative** for the N8C program. Written in N8C-1 (Neutral Foundation).
> N8C-1 builds no tables/tools/frontend — this document defines the contract the later slices
> implement. Repo code, tests, and evidence remain authoritative where they disagree.
>
> Companion docs: [`n8c-memory-classes-and-boundaries.md`](./n8c-memory-classes-and-boundaries.md)
> · [`n8c-neutral-naming-policy.md`](./n8c-neutral-naming-policy.md).

## 1. Objective

N8C turns the NAS-hosted personal assistant into a **domain-neutral, whole-life intelligence
system** that can capture, index, understand, connect, maintain, and act on information across work,
home, parenting, home ownership, coding, cooking, personal admin, hobbies, research, and future
domains — with **no new employer-specific branding** in generated content.

Shift:

```
old:  files -> index -> source cards -> search
N8C:  life/work inputs -> source identity -> cards -> claims -> decisions
        -> entities/concepts/goals/actions -> context packs -> agents/UI/automation
```

N8B's live NAS MCP (Streamable HTTP + `/health` + OAuth + origin-auth; `remote_cloudflare` read-mostly
+ the sanctioned `ai_outputs_card_upsert` write) is the **floor**; N8C builds intelligence on top and
never weakens that posture.

## 2. Ten-layer architecture

| # | Layer | Role |
|---|-------|------|
| 1 | Capture | Files, emails, calendar, Procore, schedules, financials, notes, code, receipts, research, chats. |
| 2 | Source identity | Stable source IDs, root keys, hashes, timestamps, origin, provenance, source type. |
| 3 | Source cards | Deterministic, human-readable cards linked to source records. |
| 4 | Claim layer | Atomic facts, preferences, risks, dates, commitments, decisions, contradictions. |
| 5 | Graph layer | Entities, concepts, domains, people, companies, places, tools, projects, goals, actions. |
| 6 | Worker layer | Qwen, ChatGPT, Claude, Grok, Perplexity, local code agent, future workers. |
| 7 | Context-pack layer | Bounded, sourced context packets for agents, frontend views, workflows. |
| 8 | Action layer | Drafts, reminders, task suggestions, implementation prompts, meeting prep, research briefs. |
| 9 | Feedback layer | Accepted/rejected/edited outputs, preference learning, confidence tuning. |
| 10 | Command center | Frontend UI: Today, Brain Map, Open Loops, Memory Health, Domains, Source Explorer, Qwen Jobs. |

Layers 1–3 already exist in `source_intelligence_*` (`store/source_intelligence_tables.py`, sole
reader/writer `obsidian_mcp/source_index_repository.py`, card renderer `obsidian_mcp/source_notes.py`;
`LATEST_SCHEMA_VERSION = 99`). Graph edges already have a home (`source_intelligence_relationships`
+ the card `gc-graph-links` block).

## 3. Ownership split (who owns identity vs execution)

- **NAS / backend owns**: source identity, card identity, canonical graph writes, DB mutation
  boundaries, vault write guardrails, MCP/API access, frontend data access, the Qwen job queue,
  receipts, rollback/safety checks.
- **MacBook / Qwen owns**: local model execution, enrichment generation, claim-extraction proposals,
  link suggestions, compiler outputs, lint findings, synthesis drafts.
- MacBook direct DB access is allowed for manual triage/research only — **no feature depends on it.**

Details, DB-mutation boundaries, and the four memory classes: see
[`n8c-memory-classes-and-boundaries.md`](./n8c-memory-classes-and-boundaries.md).

## 4. Consumer roles

- **Primary**: frontend UI, NAS backend API, NAS MCP.
- **Secondary**: ChatGPT, Claude, Grok, Perplexity.
- **Tertiary**: local code agent, operator scripts, future tools.

**Frontend** is a first-class consumer but reaches DB/vault/source data **only through backend
APIs** (`frontend/src/lib/api.ts` → `/api/...` → `construction/analytics/api.py`) — never direct
SQLite or NAS filesystem. **MCP** exposes purpose-built, bounded, audited tools — never broad raw
SQL (`nas_mcp/db_allowlist.py` stays narrow) or arbitrary filesystem reads. **Connected assistants**
receive redacted, bounded, source-linked results and **no raw NAS absolute paths**.

## 5. Worker (Qwen) strategy

```
NAS queues typed job -> MacBook claims -> Qwen runs Ollama qwen2.5:14b locally
  -> MacBook submits structured result -> NAS validates source/card digest
  -> NAS applies / stores / rejects, with a receipt
```

Prohibited as normal workflow: MacBook watching+freely editing the synced vault; Qwen writing
directly into canonical pages; Qwen mutating raw DB tables; Qwen owning source identity. Stale output
is rejected or stored as **advisory / not applied**.

## 6. Automation / autonomy ladder

L1 advisory-only → L2 controlled block updates → L3 compiled-page updates → L4 scheduled maintenance
autonomy → L5 broad autonomous curation **with rollback**. Autonomy increases only by operation
class, never globally; every applied model output has a receipt and rollback data.

## 7. Roadmap (N8C-0 … N8C-13)

- **N8C-0** — Repo-truth baseline from N8B *(captured in this slice's evidence `01-n8b-baseline.md`).*
- **N8C-1** — Neutral foundation *(this slice: naming policy, neutral AI-Outputs frontmatter,
  memory-class + naming docs, legacy compatibility).*
- **N8C-2** — Source/card identity hardening.
- **N8C-3** — Purpose-built read/navigation APIs + MCP tools *(the read/navigation surface — see the
  forward-pointer below — belongs here, not in N8C-1).*
- **N8C-4** — Claim extraction layer.
- **N8C-5** — Typed Qwen worker queue + first MacBook worker.
- **N8C-6** — Decision / preference / open-loop memory.
- **N8C-7** — Entity / concept / domain compiler.
- **N8C-8** — Context-pack builder.
- **N8C-9** — Frontend command center.
- **N8C-10** — Memory-health + maintenance loops.
- **N8C-11** — Research / skeptic workflow.
- **N8C-12** — Feedback / autonomy ladder.

(Subphase numbering follows the final spec's recommended implementation order; the spec's detailed
subphase list groups the same work under slightly different labels — implement in the order above.)

### Forward-pointer: read/navigation surface (N8C-3 / N8C-9)

The curated read/navigation tools — `assistant_search_sources`, `assistant_get_source`,
`assistant_get_card_for_source`, `assistant_search_cards`, `assistant_get_vault_note`,
`assistant_get_related_sources`, `assistant_graph_neighbors`, `assistant_recent_changes`,
`assistant_list_open_loops`, `assistant_list_stale_items`, `assistant_list_contradictions`,
`assistant_prepare_context_pack`, `assistant_list_enrichment_jobs`, `assistant_get_memory_health` —
are **not** built in N8C-1. They must be read-only, bounded, redacted, backed by
`source_index_repository.py`, expose **no raw SQL / no arbitrary filesystem reads / no client-facing
absolute NAS paths**, and are specified + implemented in N8C-3 (MCP/API) and consumed by the
frontend command center (N8C-9). This replaces the interim `n8c-read-navigation-surface.md` draft.

## 8. Candidate data-model additions (later slices; NOT N8C-1)

N8C extends `source_intelligence`, never replaces it. Neutral candidate tables:
`assistant_claims`, `assistant_decisions`, `assistant_preferences`, `assistant_open_loops`,
`assistant_graph_nodes`, `assistant_graph_edges`, `assistant_context_packs`,
`assistant_context_pack_items`, `assistant_enrichment_jobs`, `assistant_enrichment_receipts`,
`assistant_memory_health_findings`, `assistant_feedback_events`, `assistant_research_questions`,
`assistant_research_findings`, `assistant_research_reviews`. N8C-1 adds **none** of these.

## 9. N8C-1 non-goals (explicit)

N8C-1 builds none of: claim/decision/open-loop tables, the Qwen queue, purpose-built navigation
tools, the frontend command center, entity/concept/domain compilers, context-pack builder,
maintenance loops, feedback learning, or any schema migration (`LATEST_SCHEMA_VERSION` stays 99). It
adds **no** new write surface (the AI-Outputs `domain` param is metadata-only and does not widen
access). It ships only: the neutral naming module, neutral AI-Outputs frontmatter, local-summary
dual-READ (legacy emit retained — see naming doc), the three architecture/policy docs, and
tests/evidence.
