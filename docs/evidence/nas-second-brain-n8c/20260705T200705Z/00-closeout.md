# N8C-2 — Source/Card Identity Hardening · Closeout

> **This is N8C-2 only — NOT full N8C completion.** N8C-2 is the identity-hardening slice; claims,
> Qwen queue, navigation tools, frontend, compilers, context packs, and maintenance loops are later
> slices and are out of scope here.

- **Branch:** `ops/nas-second-brain-n8c-02-source-card-identity-20260705T200705Z`
- **Base:** `c454a581` — the corrected N8C-1 branch HEAD (`acd22926` N8C-1 implementation +
  `c454a581` N8C-1 evidence-metadata correction). N8C-1 is local-only, not on remote.
- **Schema:** unchanged, `LATEST_SCHEMA_VERSION = 99`. **No migration.** No card-rendering change.

## What landed

| Deliverable | Files |
|---|---|
| Read-only reverse-lookup + per-source card repo methods | `obsidian_mcp/source_index_repository.py` (`get_sources_for_note`, `list_cards_for_source`) |
| Identity/validation service (read-only) | `obsidian_mcp/source_card_identity.py` (new) |
| Identity contract doc | `docs/architecture/n8c-source-card-identity-contract.md` (new) |
| Tests | `tests/test_obsidian_source_card_identity.py` (new, 20 tests) |

## N8C-1 evidence correction (revision 1)

Before branching, the stale N8C-1 evidence (`00-closeout.md`/`18-git-status.md` still read "No commit
made") was corrected to record `acd22926` (not pushed) and committed as a **separate** commit
`c454a581` on the N8C-1 branch — **not** mixed into any N8C-2 commit. N8C-2 branches off `c454a581`.
See `01-n8c1-baseline-and-carryforward.md`.

## Design (zero migration, zero byte-change)

Source cards already carry `source_id` + `source_sha256` in frontmatter, so identity/lookup/stale/
duplicate/classification are delivered as a **read-only service** + one read-only reverse-lookup repo
method. `card_id` is **computed** (`sha256(source_id|note_rel_path)[:16]`, distinct from `source_id`),
not stored — avoiding a card-rendering byte change and the ~40-test byte-locked surface. Stale-by-
digest reuses the existing summary-drift pattern (card `source_sha256` vs current `content_sha256`).

## Verification

- **124 tests pass** (20 new + N8C-1 regressions + identity regressions + card-rendering/quality
  spot-check); `ruff check` clean on changed files (`10-tests.md`).
- Card rendering **byte-unchanged**: no `card_id`/`managed_by`/`card_status` added; no `hb`-branded
  metadata introduced (`test_source_card_rendering_is_byte_unchanged_and_neutral`).
- All new functions read-only: source-deleted-but-card-active is classified, never retired (`06`).

## Boundaries held

No schema migration; no Qwen queue; no claim/open-loop tables; no frontend; no new MCP tools / DB
allowlist widening; no new remote write surface; no raw/import DB mutation; no mass card rewrite; live
`hb_*` MCP tools unchanged; `remote_cloudflare` unchanged.

## Not committed / not pushed

No N8C-2 commit made — awaiting explicit authorization. `git status` in `12-git-status.md`.
