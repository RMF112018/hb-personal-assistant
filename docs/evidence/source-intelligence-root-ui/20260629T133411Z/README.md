# Evidence — A1.7 Source Intelligence External Root Management UI

**Date:** 2026-06-29
**Branch:** `feat/source-intelligence-root-ui-20260629T133411Z`
**Base commit:** `b920aee2` (origin/main — PR #213, obsidian-mcp analyzer templates)

## What shipped

An operator editor for external source roots inside **Settings → Obsidian MCP → Source
Intelligence**. Operators can add / edit / enable-disable / mark-sensitive / remove external
source roots without hand-editing `obsidian_mcp_config.json`.

### User-facing path
Settings → **Obsidian MCP** → **Source Intelligence** → **External source roots**

### Behavior
- Edits accumulate in a local **draft**; one **Save roots** button validates the whole set and
  PATCHes `external_sources` once (`patchObsidianMcpConfig`). On success the existing
  `refreshAll()` re-fetches config + source-index + watcher status.
- New-root form (key, absolute path, enabled default on, sensitive default off, fixed
  `external_file` kind) with an **Add** button.
- Editable rows: key, path, enabled, sensitive, fixed `external_file` badge, two-step **Remove**
  (Remove → Confirm remove / Cancel).
- Global controls: External source indexing enabled, External source watcher enabled (toggles,
  immediate save); Scan max files, Watch poll interval (s), Watch debounce (s) (numeric fields,
  save on blur with positive-number coercion).
- After a roots save while the watcher is running, an amber notice prompts the operator to click
  the existing **Restart** button (no silent/auto restart).

### Client-side validation (`validateRoots` / `validateRoot` in ObsidianMcpPanel.tsx)
- key required; machine-safe `^[a-z0-9_-]+$` (lowercase, digits, `-`, `_`; no spaces);
- path required and absolute (starts with `/` or `~`; backend expands `~`);
- no duplicate keys; no duplicate paths (trailing-slash normalized);
- `source_kind` always `external_file` (never user-editable).

## Backend
- **No new route, no schema/DB migration.** Persistence uses the existing
  `PATCH /api/settings/obsidian-mcp/config` → `apply_patch()` (merges + validates
  `external_sources`, preserves bearer token, writes `obsidian_mcp_config.json`).
- **One small robustness fix** (`api.py`): the PATCH handler now wraps
  `ObsidianMcpConfigPatch.model_validate(...)` and converts a pydantic `ValidationError`
  (e.g. a non-absolute external source path) into a clean **HTTP 422
  `{"detail":"invalid_obsidian_mcp_config"}`** instead of letting it escape as an unhandled 500.
  Discovered during validation; the nested entries aren't validated at the request boundary
  (request model uses `list[dict]`), so the error previously surfaced as a 500.

## Files changed
- `frontend/src/components/settings/ObsidianMcpPanel.tsx` — editor UI + state + validation helpers
- `frontend/src/components/settings/ObsidianMcpPanel.test.tsx` — new vitest suite (9 tests)
- `src/hb_assistant/construction/analytics/api.py` — 422 guard on the config PATCH handler
- `tests/test_obsidian_mcp_backend.py` — 2 new tests (external_sources persistence + token
  preservation; relative-path 422 rejection)

## Tests (see test-frontend.txt / test-backend.txt)
- Frontend: `npm run typecheck` clean; `ObsidianMcpPanel` — 9/9 pass.
- Backend: `tests/test_obsidian_mcp_backend.py` — 13/13 pass; full `-k obsidian` suite — all pass.
- Pre-existing, unrelated failures on the clean base (`SettingsPage`, `MyItemsPage`, `TodayPage`
  — 6 tests) reproduce identically with this patch reverted (verified via stash). Not introduced
  by this change.

## Manual validation (see manual-api-smoke.txt)
Live backend exercised on the real DB. Roots PATCH persisted + token preserved + no leak;
relative path → clean 422; test-event drained with a clean queue. The live
`obsidian_mcp_config.json` was backed up before and restored byte-identical after
(sha256 `bed417d9…` unchanged).

## Known gaps / follow-ups
1. Removing a root does **not** delete already-indexed source rows for that root (existing
   indexer behavior unchanged). Deferred follow-up; no destructive deletion was invented here.
2. Root-key machine-safe + dedup validation is **client-side only**. The backend accepts any
   string key (absolute-path is server-enforced). A strict backend key validator is deferred
   because it would break loading any pre-existing config whose key isn't machine-safe.
3. Watcher restart after a roots change is operator-driven (prompted), not automatic — the
   watcher reads roots at start, so `source-watch/status.roots` reflects the saved roots only
   after a restart.
