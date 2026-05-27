# 00 — Project Context and Objective

## Repository

`RMF112018/hb-personal-assistant`

## Known Starting Point

Phase 14 Prompts 0–8 were reportedly executed and closed through:

`baac7b5cf61d461d3b544262d02ad4c051aa9fa1`

Prompt 9 remains pending because Microsoft Graph delegated permissions / tenant-admin consent remain delayed.

## Current Objective

Convert the current local-runtime implementation into an MVP candidate by auditing actual repo-truth, fixing local code/doc mismatches, proving deterministic local operation, tightening quality gates, and producing an operator-facing evidence package.

## MVP Definition for This Phase

The MVP is not “full Microsoft 365 connected assistant.” The MVP is:

- A Bobby-only local-first assistant.
- It can run locally without Graph consent.
- It classifies Graph consent as an external blocker.
- It continues local stages when Graph is unavailable.
- It extracts source-linked action/workstream intelligence from local/store/fixture inputs.
- It generates a marker-bounded Obsidian brief.
- It preserves user-authored Obsidian content outside managed markers.
- It emits redacted evidence and run ledger entries.
- It remains privacy-safe and writeback-free.

## Explicit Non-Goals

- No Microsoft 365 writeback.
- No app-only runtime mail/calendar workaround.
- No multi-user support.
- No cloud state.
- No autonomous external actions.
- No dependency on IT completing consent for the local MVP proof.
- No broad refactor beyond hardening MVP-critical paths.

## Success Classification

```text
MVP_CANDIDATE_LOCAL_RUNTIME_READY
GRAPH_DELEGATED_PROOF_DEFERRED_PENDING_ADMIN_CONSENT
```
