# N8C-1 — Neutral Foundation · Closeout

> **This is N8C-1 only — NOT full N8C completion.** N8C-1 is the first of the N8C-0…N8C-13 slices.
> It establishes the neutral naming foundation; the claim layer, Qwen queue, navigation tools,
> frontend, compilers, context packs, maintenance loops, and research/feedback workflows are all
> later slices and are explicitly out of scope here.

- **Branch:** `ops/nas-second-brain-n8c-01-neutral-graph-20260705T185844Z`
- **Base:** `origin/main` @ `e80f3729c661a98daa04c2d393b19fce253eeb94` (live N8B NAS MCP)
- **Schema:** unchanged, `LATEST_SCHEMA_VERSION = 99`. No migration, no new write surface.

## What landed

| Deliverable | Files |
|---|---|
| Neutral naming module (+ `CREATED_VIA_MCP`, `sanitize_domain`) | `src/hb_assistant/naming.py` |
| AI-Outputs neutral frontmatter (`managed_by`/`note_type`/`domain`/`created_via`) | `nas_mcp/ai_outputs.py`, `nas_mcp/tool_registration.py`, `nas_mcp/broker.py` |
| Local-summary **dual-READ** (legacy emit retained) | `obsidian_mcp/source_notes.py`, `source_local_summary.py`, `source_card_repair.py`, `scripts/obsidian_source_card_append_local_summary.py` |
| Architecture / memory-class / naming docs | `docs/architecture/n8c-personal-intelligence-operating-layer.md`, `n8c-memory-classes-and-boundaries.md`, `n8c-neutral-naming-policy.md` |
| Tests | `tests/test_nas_mcp_ai_outputs.py`, `test_obsidian_source_card_local_summary_marker.py`, `test_nas_mcp_remote_profile.py` (extended) |

## Docs coverage (deliverable proof)

| Required doc | File | Key sections |
|---|---|---|
| Operating layer | `n8c-personal-intelligence-operating-layer.md` | objective, 10-layer, ownership split, consumer roles, Qwen strategy, autonomy ladder, N8C-0…13 roadmap, read/nav forward-pointer, non-goals |
| Memory classes & boundaries | `n8c-memory-classes-and-boundaries.md` | 4 classes, DB mutation boundary, vault write boundary, `.eml` model, ownership |
| Neutral naming policy | `n8c-neutral-naming-policy.md` | policy, AI-Outputs frontmatter contract + `domain` sanitizer, local-summary dual-read/deferred-emit, live-tool + legacy-marker compat |

## Verification

- **222 tests passed** (targeted N8C-1 + regression set); `ruff check` clean on all changed files (`08-tests.md`).
- End-to-end smoke via `NasMcpBroker.dispatch`: `domain` sanitized + path-inert; `created_via` server-fixed; folder-lock intact (`02-neutral-naming-proof.md`).
- No new employer-branded generated content; live MCP tool names unchanged; `remote_cloudflare` stays read-mostly + AI-Outputs-write-only.

## Not committed / not pushed

No commit made — awaiting explicit authorization. `git status` in `18-git-status.md`.
