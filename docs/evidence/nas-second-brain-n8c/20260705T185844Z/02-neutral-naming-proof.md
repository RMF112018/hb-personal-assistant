# 02 — Neutral Naming Proof

## Naming module
`src/hb_assistant/naming.py` (new, dependency-free) is the single source of neutral generated-content
identifiers: `MANAGED_BY="personal_assistant"`, `NOTE_TYPE_AI_OUTPUT="ai_output"`,
`CREATED_VIA_MCP="mcp"`, `DOMAIN_UNKNOWN="unknown"`, `sanitize_domain()`, neutral + legacy
local-summary markers, dual-form predicates, and forward vocabulary for later slices.

## AI-Outputs frontmatter change (`nas_mcp/ai_outputs.py::_render_card`)

```diff
         f"source_client: {source_client}",
-        "hb_managed: ai_outputs_card",
+        f"managed_by: {MANAGED_BY}",
+        f"note_type: {NOTE_TYPE_AI_OUTPUT}",
+        f"domain: {domain}",
+        f"created_via: {CREATED_VIA_MCP}",
```

Rendered new card (smoke via `NasMcpBroker.dispatch`, `domain="Home Ownership"`):
```
---
title: Home Reno Plan
tags: []
source_client: chatgpt
managed_by: personal_assistant
note_type: ai_output
domain: homeownership
created_via: mcp
---
```

## No-readers proof (safe to drop `hb_managed`)
After the change, `grep -rn "hb_managed"` / `"ai_outputs_card"` (excluding tool name
`ai_outputs_card_upsert`) across `src/ tests/` returns only the new **test assertions checking
absence**. No parser/verifier/tool reads the old marker; update uses `patch_note`+SHA, append uses
file+SHA. Dropping it breaks nothing.

## `domain` sanitizer — bounded, path-inert, metadata-only (clarification 1)
`naming.sanitize_domain`: optional (default `unknown`), lowercased, reduced to `[a-z0-9_-]`
(strips YAML-special chars, whitespace, path separators, `.`/`..`, NUL), length ≤ 40, empty/invalid →
`unknown`. Never contains a separator; never used to build a path.

Smoke proof (hostile input via broker):
```
domain "../../../etc/shadow"  -> frontmatter "domain: etcshadow"  | /etc/shadow escaped: False
domain "///"                  -> frontmatter "domain: unknown"
path always: AI Outputs/<title>.md   (domain never affects path)
```

## `created_via` is server-fixed (clarification 2)
Passing `created_via: "HACKED"` in the dispatch args is **ignored** (not a tool param). The card
always shows `created_via: mcp`; `"HACKED"` never appears. Only `domain` is caller-supplied.

## Safety preserved
Folder-lock, SHA-gated update, append size re-check, backup-before-overwrite, receipts, client/mode
validation, and caps are untouched — verified green by the NAS MCP test suite (`08-tests.md`).

## Branding classification (no new employer branding introduced)
- **Changed (a):** removed `hb_managed: ai_outputs_card`; new cards neutral.
- **Kept for compat (b):** live `hb_*` MCP tool names (not renamed/removed; aliases deferred).
- **Documented debt (a/defer):** local-summary emit (dual-read now; emit flip = N8C-2, see `06`);
  other `hb-*` markers, OAuth/app-shell HTML, `hb_project_number` template key, `Work/HB Personal
  Assistant/` output prefix — unchanged in N8C-1.
- **Left (c):** `hb_assistant` package + `hb_project_*` data fields (not generated branding).
- **Left (d):** historical `docs/evidence/**`. (Clarification 4/6: no rename/removal of live tools;
  no rewrite of historical evidence or old cards for branding.)
