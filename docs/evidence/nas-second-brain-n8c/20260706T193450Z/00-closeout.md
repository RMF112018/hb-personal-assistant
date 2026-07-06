# N8C-7 — Source-Backed Entity/Concept/Domain Memory Compiler

**Status:** implemented + tested + evidence. **NOT committed** (commit not authorized by the task).
**Push:** none. **PR:** none. **Merge:** none.

## Baseline & branch
- N8C-6 base commit: `c9866927207190a8cae092125107148285d6f46d` (`feat(nas): add n8c context pack builder`).
- N8C-7 branch: `ops/nas-second-brain-n8c-07-memory-compiler-20260706T193450Z` (branched from `c9866927`).
- Preflight: working tree started at `c9866927`, `LATEST_SCHEMA_VERSION = 102`, no
  `src/hb_assistant/agent_bridge/` (no N8D in this worktree).
- Worktree: `/Users/bobbyfetting/hb-pa-n8c02-20260705T200705Z` (operator-local; context only).

## What N8C-7 adds
A deterministic, **no-LLM** memory compiler that turns the N8C substrate (candidate claims, context-pack
items, enrichment summaries, backlink targets) into durable, **source-backed** memory objects an
operator / ChatGPT can review — without Qwen owning truth, vault mutation, claim auto-acceptance, or any
N8D bridge/orchestration.

## Schema / migration status
- New head: **`LATEST_SCHEMA_VERSION = 103`**, migration `v103_assistant_memory` (wiring mirrors V102).
- Four additive memory-owned tables (`store/assistant_memory_tables.py`, 9 indexes):
  `assistant_memory_nodes`, `assistant_memory_mentions` (table CHECK: ≥1 provenance anchor),
  `assistant_memory_compilations`, `assistant_memory_events` (lifecycle-only).
- Additive + idempotent; V100/V101/V102 rows and tables survive. Details: `03-schema-and-contract.md`.

## Changed / new files (9 modified + 10 new; full list in `13-git-status.md`)
New source: `store/assistant_memory_tables.py` (V103 DDL), `obsidian_mcp/memory_models.py`
(enums/normalize/deterministic ids/caps), `obsidian_mcp/memory_repository.py` (sole reader/writer of the
4 memory tables), `obsidian_mcp/memory_compiler.py` (discovery + compile), `cli/memory.py`.
New tests: `test_memory_v103_migration.py`, `test_memory_repository.py`, `test_memory_compiler.py`,
`test_fastapi_analytics_memory.py`, `test_nas_mcp_memory.py`.
Modified: `store/migrator.py` (V103 wiring + head bump), `construction/analytics/api.py` (5 GET routes),
`cli/main.py` (typer registration), `nas_mcp/{profile,broker,tool_registration}.py` (gate + allowlist +
read-only-snapshot dispatch + gated tool block), and three existing migration/head tests updated for the
V103 head bump.

**Not touched:** N8D / `agent_bridge/`, source/card rendering, `construction/second_brain/`, the vault,
and every raw/import/source/claim/enrichment/context-pack table.

## Compiler contract (advisory, deterministic, source-backed)
- Discovery is **pack-scoped**: `discover_memory_candidates(pack_id)` reads a context pack's items —
  claim `normalized_subject`/`normalized_object` → entity nodes (raw `claim_text` fallback → a
  lower-confidence, `needs_operator_review` concept node), `source_summary` → a source-topic node
  (Qwen-derived → `needs_operator_review`), `backlink_target` → a topic node (`low_confidence`).
- Deterministic identity → idempotent: unchanged normalized identity keeps `node_id`; same anchor keeps
  `mention_id`; a changed node `input_digest` yields a NEW `compilation_id` and supersedes the prior
  `built` compilation for that `(node, compile_type)`. No node-merge / operator-disposition
  (`merged`/`archived` reserved for a future slice).
- Every node has ≥1 provenance-backed mention; compilations are bounded (summary/key-points caps,
  `truncated`/`stale_count` recorded); a node inherits its **worst** mention tier.
- Compiled memory is **ADVISORY** — node `status`/`review_tier`/a compilation NEVER imply a claim was
  accepted; the compiler only READS claims (they stay candidate/unreviewed).

## Exposure (all read-only; one CLI writer) — `09-api-cli-mcp-exposure-proof.md`
- **API:** 5 read-only GET routes under `/api/assistant/memory/*` (bounded, `_assistant_env` guardrails,
  relative-path only, coded 404s). No write route.
- **CLI:** `hb-assistant memory preview|compile|export|list` — read-only default; `compile --pack-id`
  required (pack-scoped, no global compile-all), `--apply` the sole writer (memory tables only).
- **MCP:** 4 read-only remote tools gated by default-ON `assistant_memory_enabled()` (kill-switch
  `HB_MCP_ASSISTANT_MEMORY=0`), served from the read-only DB snapshot (`mode=ro&immutable=1` +
  `PRAGMA query_only=ON`). 12 nav + 4 context-pack + 4 memory = 20 `assistant_*` tools preserved;
  `ai_outputs_card_upsert` remains the ONLY sanctioned remote write. No build/apply/write/compile tool.

## Boundary proofs — `10-no-raw-no-writeback-proof.md`
No mutation outside the 4 memory tables (preview/dry-run/apply row-count checks) · claims stay
candidate/unreviewed · no raw `result_json`/body/prompt persisted (bounded excerpts + digests) · bounded
JSON export (relative paths, no abs path) · idempotent (same input no dup; changed input new+supersede) ·
no vault / no rendering change / no startup compiler / no N8D / no vector store.

## Verification — `11-tests.md`
- New N8C-7 tests: **38 passed**.
- N8C-1→7 regression set: **293 passed, exit 0** (pass-dot + exit-0 derivation).
- `scripts/test-schedule.sh -q` (migrator/schema canary for V103): **exit 0** (335 tests).
- `ruff check` on in-scope changed source: **PASS**; api.py additions add zero new findings.
- CLI/API/MCP smoke on a temp migrated DB: green.

## Commit posture
**Working tree remains uncommitted.** N8C-7 commit NOT authorized — stopped before commit. No push, no
PR, no merge. Plain commit message only + no AI co-author trailer when/if a commit is later authorized.
