# Defect fix (PR #216, pre-merge) — wire `source_card_auto_max_per_drain` end-to-end

## Defect
A1.8 added `source_card_auto_max_per_drain` to `ObsidianMcpConfig` (+ patch model + validator) and
to `source_indexer.drain_queue`, but it was **not** wired through the settings API request model or
the frontend. An operator `PATCH source_card_auto_max_per_drain=25` was silently dropped (the API
request model `ObsidianMcpConfigPatchRequest` lacked the field, so `request.model_dump(exclude_none=
True)` never carried it into `apply_patch`). Safety-control defect: broad source roots could
generate too many deterministic cards because the per-drain cap was not operator-adjustable.

## Fix
1. **`src/hb_assistant/construction/analytics/api.py`** — added
   `source_card_auto_max_per_drain: int | None = None` to `ObsidianMcpConfigPatchRequest`
   (mirrors `source_summary_auto_max_per_drain`). PATCH now carries it into `apply_patch`, which
   persists it; the response (`config.redacted()` = `model_dump` minus token) already exposes it.
2. **`frontend/src/lib/api.ts`** — added a typed `ObsidianMcpConfigPatch` interface (known
   source-intelligence controls incl. `source_card_auto_max_per_drain?: number`, with an index
   signature for back-compat) and typed `patchObsidianMcpConfig` to it.
3. **`frontend/.../ObsidianMcpPanel.tsx`** — added a visible **"Card auto max per drain"** numeric
   `Field` next to the auto-generation controls, seeded from config and saved on blur via the
   existing `commitNumericField` (positive-int) → `saveConfig({ source_card_auto_max_per_drain })`.

## Tests added
- Backend `test_obsidian_mcp_backend.py::test_config_update_persists_source_card_auto_max_per_drain`
  — PATCH `=25` returns it in the config and `load_config()` persists `25`; GET reflects it.
- Indexer `test_obsidian_source_rebuild_autogen.py::test_rebuild_uses_configured_card_cap_not_default`
  — with cap `1` the first rebuild drain generates exactly 1 card (configured value, not the 200
  default / not None), and the remainder resumes to 3.
- Frontend `ObsidianMcpPanel.test.tsx` — "displays the card auto-max-per-drain control seeded from
  config" and "submits the card auto-max-per-drain value on blur" (PATCH carries `25`).

## Secondary fix found while testing
The cap=1 indexer test surfaced a latent bug: the `drain_queue` else-branch (single-file/reindex
events) gated card generation on `cards_done < card_cap` and **dropped** the card without
re-enqueueing, so with a small cap the resumed overflow files never got cards. Corrected so the
`card_cap` bounds only the rebuild scan-burst (which re-enqueues overflow as `reindex_requested`),
while single-file events generate their one card (naturally bounded by the claim batch); summaries
remain capped via `summaries_remaining`.

## Proof
- `defect-fix-grep-after.txt` — `source_card_auto_max_per_drain` now present in `api.py`,
  `frontend/src/lib/api.ts`, `ObsidianMcpPanel.tsx`, and `ObsidianMcpPanel.test.tsx` (plus the
  original `config.py` / `source_indexer.py`).
- `defect-fix-test-output.txt` — backend 2/2 + frontend 16/16.
- No schema/migration change. No unrelated behavior changed.
