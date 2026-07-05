# 17 — Risk & Defer List

## Deferred to N8C-2 (explicit compatibility debt)
1. **Local-summary neutral EMIT flip.** N8C-1 ships dual-READ only; the emitter stays legacy. N8C-2
   must: point `source_notes.LOCAL_SUMMARY_*` at `naming.LOCAL_SUMMARY_*`; dual-count the validity
   guard in `scripts/obsidian_source_card_rerender_existing.py:200-202`; update the ~8
   hardcoded-marker test files (retain a legacy-compat case); add a legacy→neutral
   migration-on-`replace` test. Readers are already forward-compatible → additive. (See `06`.)

## Documented neutrality debt (unchanged in N8C-1)
2. Other managed markers (`hb-project-identity`, `hb-email*`, `hb-schedule-*`, `HB-DAILY-BRIEF`,
   Procore/data-quality families) — read-back-compat + emit flip per family.
3. OAuth/app-shell HTML (`HB NAS MCP`, `HB Obsidian MCP`, "HB Assistant") — text-only, live auth
   surface; dedicated branding slice.
4. `hb_project_number` template key; `Work/HB Personal Assistant/` output-path prefix.
5. **Neutral aliases for live `hb_*` MCP tool names** — deferred to keep the live ChatGPT/Claude/Grok
   connectors stable; old names kept, aliases added + deprecated slowly in a later slice
   (clarification 4).

## Out of scope for N8C-1 (later slices; clarification 8)
6. No schema migration (`LATEST_SCHEMA_VERSION` stays 99); no Qwen queue; no claim/decision/open-loop
   tables; no frontend work; no new write surface; no broad SQL/filesystem exposure. The AI-Outputs
   `domain` param is metadata-only and does not widen access.

## Stop-condition check — none tripped
No live MCP tool renamed/removed; no card corruption (dual-read + tests); `remote_cloudflare` write
gates + AI-Outputs folder-lock intact (verified: hostile `domain` cannot escape the folder); no raw
DB mutation; no broad DB/filesystem access; no secrets touched; no new employer branding in generated
content.
