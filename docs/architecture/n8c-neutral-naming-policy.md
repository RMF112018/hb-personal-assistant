# N8C — Neutral Naming Policy & Compatibility Plan

> Status: **contract / normative**. Written in N8C-1. Companion:
> [`n8c-personal-intelligence-operating-layer.md`](./n8c-personal-intelligence-operating-layer.md).

## 1. Policy

New generated vault content, new public tool names, new user-facing UI, and new architecture
contracts are **domain-neutral** — no expansion of `hb_*`/employer branding. Single source of truth:
`src/hb_assistant/naming.py` (dependency-free; imported downward by both the NAS AI-Outputs writer
and the Obsidian card renderer, so it never inverts the `nas_mcp → obsidian_mcp` arrow).

Preferred identifiers: `assistant`, `personal_assistant`, `second_brain`, `source_card`,
`local_summary`, `enrichment`, `context_pack`, `memory_graph`. Consumed in N8C-1: `MANAGED_BY =
"personal_assistant"`, `NOTE_TYPE_AI_OUTPUT = "ai_output"`, `CREATED_VIA_MCP = "mcp"`, the neutral
`assistant-local-summary` markers + dual-form predicates, and `sanitize_domain()`.

## 2. AI-Outputs card frontmatter contract

New AI-Outputs cards (`nas_mcp/ai_outputs.py::_render_card`) carry:

```
title: <caller title>
tags: [<sorted, deduped>]
source_client: chatgpt|claude|grok|local|unknown   # allowlisted
managed_by: personal_assistant                     # server constant
note_type: ai_output                               # server constant
domain: <sanitized label>                          # metadata-only, see §2.1
created_via: mcp                                    # server-fixed, NOT caller-supplied
```

The legacy `hb_managed: ai_outputs_card` key is **no longer written** (grep-proven zero readers).
Existing cards are not migrated: append preserves them; a full update re-renders them neutral. All
safety properties are unchanged (folder-lock, SHA-gate, backup, receipts, mode validation, caps).

### 2.1 `domain` sanitizer (metadata-only, path-inert)

`naming.sanitize_domain(value)`: optional (default `"unknown"`), lowercased, reduced to
`[a-z0-9_-]` (removing YAML-special chars, whitespace, path separators, `.`/`..` traversal, NUL),
length-bounded to 40, and collapsing empty/`None`/invalid input to `"unknown"`. The result is a
single YAML-safe token that **never contains a path separator and is never used to build a path** —
it is card metadata only. `domain` is a free-form label (so future domains need no code change), not
an allowlist. `created_via` is fixed server-side to `mcp` and is **not** accepted from callers.

## 3. Local-summary marker — dual-READ now, neutral EMIT deferred (N8C-2 debt)

N8C-1 makes every local-summary reader recognise **both** the neutral `assistant-local-summary` and
legacy `hb-local-summary` forms (`source_notes.py`, `source_local_summary.py`, `source_card_repair.py`,
`scripts/obsidian_source_card_append_local_summary.py`). The **emitter intentionally stays on the
legacy marker** this slice — `source_notes.LOCAL_SUMMARY_*` alias `naming.LEGACY_*` — because flipping
it is a wide, cosmetic-only change: a second validity-guard matcher
(`scripts/obsidian_source_card_rerender_existing.py:200-202`) plus ~8 hardcoded-marker test files.

> **N8C-2 compatibility debt:** flip the emitter to `naming.LOCAL_SUMMARY_*`, dual-count the rerender
> validity guard, update the ~8 hardcoded-marker tests, and add a legacy→neutral migration-on-replace
> test. Readers are already forward-compatible, so the flip is additive.

## 4. Live-tool + legacy-marker compatibility

- **Live `hb_*` MCP tool names** are **not renamed or removed** in N8C-1 (would risk the live
  ChatGPT/Claude/Grok connectors). Neutral aliases are **deferred** to a later slice; when added, old
  names stay and are deprecated slowly (precedent: `construction_daily_brief_packet` aliases
  `hb_daily_brief_packet`).
- **Other legacy managed markers** (`hb-project-identity`, `hb-email*`, `hb-schedule-*`,
  `HB-DAILY-BRIEF`, Procore/data-quality families), OAuth/app-shell HTML (`HB NAS MCP`,
  `HB Obsidian MCP`), the `hb_project_number` template key, and the `Work/HB Personal Assistant/`
  output-path prefix are **documented neutrality debt**, unchanged in N8C-1.
- Internal Python package/module names (`hb_assistant`, `hb_project_key`/`hb_project_number` data
  fields) are **left as-is** — not generated branding.

Historical `docs/evidence/**` and code comments are left untouched.
