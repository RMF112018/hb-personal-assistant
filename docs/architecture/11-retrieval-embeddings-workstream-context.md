# 11 — Retrieval, Embeddings And Workstream Context

**Version**: 1.1.0 (Prompt 11)
**Status**: Complete
**Date**: 2026-05-25

## Overview

Prompt 11 implements the retrieval layer for the HB Personal Assistant MVP, enabling deterministic keyword + gated semantic search over the redacted, source-linked content produced by prior phases (primarily parser_outputs excerpts from Phase 9/10, plus action items, etc.).

Per 02 plan row 9: "deterministic retrieval, then gated sqlite-vec semantic retrieval".

In v1.1 MVP: pure-python implementation (no heavy vector DB deps or sqlite-vec extension required at runtime for core path; table added for future sqlite-vec). Embeddings via local Ollama (nomic-embed-text recommended) with deterministic fallback. WorkstreamContext assembler for daily/ focus use cases (feeds briefs, actions, etc.).

All outputs redacted/bounded, carry SourceLink provenance, dry-run/mock friendly, no M365 writes, no full content leakage.

## Components

- `src/hb_assistant/retrieval/embedder.py`: OllamaEmbedder (requests to localhost:11434/api/embeddings, graceful fallback to hash-based pseudo-vec for demo/offline) + DeterministicEmbedder for tests/CI.
- `src/hb_assistant/retrieval/retriever.py`: Retriever — loads candidates from parser_outputs (via new Store helper), scores with keyword overlap (det), optional blend with cosine on embedded query vs candidate vecs. Returns RetrievalHit with excerpt (bounded), score, links.
- `src/hb_assistant/retrieval/context.py`: WorkstreamContext + Builder — assembles retrieved hits + recent actions + (future mentions) into redacted bundle for a target date/focus. Used by future orchestration / brief enhancement.
  - Phase 15 Prompt 04: `mentions` is now first-class (populated from `store.list_recent_body_mentions` in `build_for_today()`; redacted metadata only; existing consumers receive the data directly on the context object).
- Store extensions (repositories.py + migrator.py): list_recent_parser_outputs, content_embeddings table (for persisted vecs in future), migration safe additive.
- CLI: `hb-assistant search "query" --json` (top-level, wired; thin safe redacted results). Removed search from stub list.
- Exports: hb_assistant.retrieval
- Tests: test_retrieval.py (embedder, retriever det+sem, context, leak/redaction guards) — all green.

No new runtime pip deps (uses requests + stdlib math; Ollama optional for semantic quality).

## Pipeline

```
Store (parser_outputs excerpts + actions, redacted + linked)
  → load candidates (bounded recent)
  → deterministic keyword score (overlap + phrase boost)
  → [if enabled] embed(query) + embed(candidates) + cosine blend
  → top-k hits (excerpts + provenance links + scores)
  → WorkstreamContext (for date/focus) → consumers (brief, actions, future synth)
```

Gated: semantic_enabled flag / env; falls back silently to det on embed errors (no Ollama, no model, net issues).

## Decisions & Tradeoffs (v1.1)

- Pure python cosine + json vec storage (or onfly) instead of sqlite-vec / chromadb for MVP: zero extra deps, works everywhere, sufficient for personal scale (<~few thousand chunks).
- Table content_embeddings added (for future persisted + sqlite-vec or external index) but not yet populated in v1.1 (onfly embed for candidates).
- Ollama for real embeddings (local, private, matches model routing spec from 10); fallback det for always-working demo/tests. Recommend `ollama pull nomic-embed-text`.
- Focus on parser_outputs as primary corpus (the "work product" from files after selective ingest Phase 10). Email previews not long-term persisted in schema (flags only from Phase 6).
- No FTS5 virtual table (portability); python keyword sufficient + semantic for recall.
- Redaction: hits always carry only the bounded excerpts already produced/stored by prior phases; no reconstruction of full files or bodies.
- CLI thin (search top-level like files); full integration in morning/automation later (Prompt 12+).
- Version 1.1.0 (minor feature after 1.0.0 milestone).

## Mermaid

```mermaid
flowchart TD
  subgraph Sources[Phase 9/10 + earlier]
    PO[parser_outputs<br/>text_excerpt bounded redacted]
    Actions[action_items]
    Links[Source Links]
  end
  subgraph Retrieval[Phase 11]
    Load[Load candidates<br/>Store helpers]
    Det[Deterministic score<br/>keyword overlap]
    Sem[Embed (Ollama or det fallback)<br/>+ cosine blend]
    Rank[Rank + top-k]
    Ctx[WorkstreamContext<br/>date/focus bundle]
  end
  PO --> Load
  Actions --> Load
  Load --> Det
  Det -->|semantic| Sem
  Sem --> Rank
  Rank --> Ctx
  Links --> Ctx
  Ctx --> Consumers[Brief / Actions / Future synth / CLI search]
  Note[redacted excerpts only<br/>links preserved<br/>gated semantic<br/>pure python fallback] -.-> Sem
  CLI[search "query" --json] --> Rank
```

## Integration & Refs

- 02 row 9 (retrieval)
- 08/09/10 (excerpt sources + selective ingest + parser matrix)
- 05/07 (store, actions)
- 06 (classification signals for future boosting)
- 08 (brief consumption of context)
- 03/06/13-15/20 (redaction, dry-run, gates, no full content)
- 10 model routing (embeddings role "supplemental semantic retrieval")
- New table in resources/sqlite-schema.sql (additive)
- Evidence: phase-11 samples with redacted hits + traces; proof of no leaks beyond source excerpts.

## Next

Prompt 12: Launchd automation + diagnostics hardening (cron-like local automation for morning run, using retrieval context + prior phases).

Guardrails: read-only, excerpts only, source-linked, tests green, v1.1.0, sensitive scan clean.

Ready for richer context in automation and synthesis.
