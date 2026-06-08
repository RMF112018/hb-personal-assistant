# 217. Phase 10A — Source-ref aliases for live action extraction

Date: 2026-06-08

Package: HB Construction Intelligence — Phase 10 / 10A Local Action Intelligence (repo-truth update)

## Context

Follow-up to ADR 216. Live extraction reaches Ollama and returns coherent object-root candidates, but
local models cannot reproduce long canonical Graph/thread/event IDs — a good candidate cited
`source_refs: ["<excerpt1>"]` and was (correctly) rejected `source_ref_not_in_packet`. Fix: give each
known packet source a short deterministic alias (`src_1`, `src_2`, …), have the model cite aliases, and
resolve aliases → canonical refs before schema/business validation and persistence. Canonical-ref
backward compatibility is preserved. All changes are in
`construction/second_brain/local_ai/raw_action_intelligence.py` + tests (no schema/migration/contract).

## Decision

### Deterministic alias map
After `known_family`, `extract_action_candidates_from_raw` builds `alias_to_ref` over the union of known
refs — **packet source_refs first (thread → message/event), then excerpts** — so the thread ref is
`src_1` for a thread packet and the event is `src_1` for a calendar packet. It also builds `ref_to_alias`
and `allowed_source_aliases` (`[{alias, source_family}]`).

### Alias-aware prompt
`_build_prompt(excerpts, ref_to_alias, allowed_source_aliases)` shows `source_alias: src_N` +
`source_family` + content per excerpt (no long raw refs in the header), an example using `"source_refs":
["src_1"]` (clearly labelled an example), explicit rules (aliases only; never `<excerpt1>`/labels/
shortened/invented/long raw IDs; ≥1 valid alias), and a trailing `allowed_source_aliases` JSON block.
`STRICT_ACTION_SYSTEM` states `source_refs` are aliases from `allowed_source_aliases`.

### Resolve before validation/persistence
`_resolve_source_refs(refs, alias_to_ref, known_family)` maps alias → canonical, canonical-known →
itself (backward compat), else unresolved. In the accept phase, a candidate with any unresolved ref is
rejected `source_alias_not_in_packet` (offending tokens — safe labels — included, never raw content);
otherwise `cand = cand.model_copy(update={"source_refs": resolved})` so persistence uses canonical refs
and `source_family` stays authoritative (thread→email_thread_raw_context, message→
email_message_raw_content, event→calendar_event_raw_content). This replaces the prior
`source_ref_not_in_packet` check. No string guessing.

### Diagnostics
Adds `source_alias_count`, `candidate_refs_resolved_count`, `candidate_refs_unresolved_count`,
`unresolved_ref_reason` to the safe diagnostics block. Aliases/labels only — no raw body/subject/URL/
token. (A `parse_meta.update(...)` was written as a dict-merge to satisfy the no-writeback scanner.)

## Verified (mock)

| Model `source_refs` | result |
| --- | --- |
| `["src_1"]` (thread packet) | accepted → canonical thread ref, `email_thread_raw_context`, persisted |
| `["src_1"]` (calendar packet) | accepted → `calendar_event_raw_content` |
| `["src_2","src_3"]` (related) | message + event families preserved |
| `["<excerpt1>"]` / `["src_999"]` | rejected `source_alias_not_in_packet`, nothing persisted |
| `["m1"]` (canonical) | accepted (backward compat) |

## Guardrails / non-goals

No live `--apply`; no email send / calendar mutation / Procore / MCP-raw / cloud-LLM. Dry-run default;
diagnostics redacted. No schema/migration/contract-JSON change, no README/ledger bump. No apply-path live
persistence is recommended until a live dry-run returns accepted candidates or explicit schema/business/
unresolved-alias rejections.
