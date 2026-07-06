# 02 — Claim Layer Current-State Audit

## Pre-N8C-4 state
No claim tables existed. Sources/cards/navigation (N8C-1..3) could find and read content, but there was
no durable, source-backed atomic-claim memory. `source → card → search` had no
`claim candidates → validated claim records` layer above it.

Note: an unrelated `second_brain_retrieval_unsupported_claim_checks` table exists (retrieval-guard
telemetry) — NOT a claim store; N8C-4 does not touch it. The `assistant_*` table namespace is
established (`assistant_runs`, V1), so `assistant_claims` fits repo convention.

## What N8C-4 adds (narrow, neutral)
Exactly two additive tables (`assistant_claims`, `assistant_claim_events`) at schema V100 — NOT a graph
schema, no entity/concept/domain compiler, no decision/open-loop/preference subsystem. Decision /
preference / task / contradiction are represented merely as **claim types**, not subsystems.

## Deliberately deferred (out of scope this slice)
Qwen worker queue, Ollama, autonomous model extraction, decision/preference/open-loop workflows,
context packs, graph compiler, frontend command center, research/skeptic, feedback learning,
maintenance loops, broad MCP write tools, `db_allowlist` expansion, raw/import DB mutation, mass
vault/card rewrite, remote claim tools. The ingestion seam reserves `extracted_by="future_qwen"` so a
later model path needs no schema change.
