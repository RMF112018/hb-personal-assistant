# N8C-8 — Decision, Preference, and Open-Loop Memory Layer

**Status:** implemented + tested + evidence. **NOT committed** (commit not authorized by the task).
**Push:** none. **PR:** none. **Merge:** none.

## Commits & branch
- N8C-6: `c9866927` (`feat(nas): add n8c context pack builder`).
- N8C-7: **`b99151f1`** (`feat(nas): add n8c memory compiler`) — committed in Part 1 this session
  (staged-only, no AI trailer, not pushed).
- N8C-8 branch: `ops/nas-second-brain-n8c-08-decision-open-loop-memory-20260706T203541Z`, base `b99151f1`.
- Preflight: `LATEST_SCHEMA_VERSION = 103`, no `agent_bridge/` (no N8D) → N8C-8 = **V104**.

## What N8C-8 adds
A deterministic (NO-LLM) extractor that turns the N8C substrate (claims, context-pack items, memory
compilations) into durable, **advisory, source-backed** decision / preference / open-loop records — the
reviewable personal-intelligence layer. Records are advisory: nothing is executed, sent, scheduled, or
auto-accepted; source truth is never mutated; no N8D orchestration is duplicated.

## Schema / migration
- Head **`LATEST_SCHEMA_VERSION = 104`**, migration `v104_assistant_decision_memory` (mirrors V103).
- Four additive N8C-8-owned tables: `assistant_decision_records`, `assistant_preference_records`,
  `assistant_open_loop_records` (each: table CHECK ≥1 provenance anchor), and a shared
  `assistant_decision_memory_events` (lifecycle-only). Additive + idempotent; V100–V103 survive.
  Details: `03-schema-and-contract.md`.

## Changed / new files (10 modified + 10 new; full list `13-git-status.md`)
New source: `store/assistant_decision_memory_tables.py` (V104 DDL), `obsidian_mcp/
decision_memory_{models,repository,extractor}.py`, `cli/decision_memory.py`. New tests: 5 files.
Modified: `store/migrator.py` (V104 wiring), `construction/analytics/api.py` (6 GET routes), `cli/main.py`,
`nas_mcp/{profile,broker,tool_registration}.py` (gate + 6 read-only MCP tools),
`obsidian_mcp/memory_repository.py` (one READ-ONLY helper), and three migration/head tests updated for V104.
**Not touched:** N8D/`agent_bridge/`, source/card rendering, vault, and every raw/claim/enrichment/
context-pack/memory table (only the 4 N8C-8 tables are written).

## Model summaries
- **Decision:** `decision_id` (=`sha256(identity_key|evidence_digest)`), advisory `status=candidate`/
  `review_state=unreviewed`; from `decision_candidate` claims. Advisory, never claim acceptance.
- **Preference:** `preference_id`; `user_preference` from `preference` claims (strength from confidence);
  `workflow_preference` weak tier from memory compilations (`compilation_derived`, `needs_review`).
- **Open loop:** `open_loop_id`; commitment/task_candidate/risk_followup from claims; `question` from a
  conservative bounded heuristic (≤0.35 conf, `needs_review`). Never executed — identify/store/list/label only.
- **Provenance:** every record carries ≥1 anchor (DB CHECK + model guard) + bounded evidence + digests.
- **Idempotency & supersede:** deterministic ids; same input → no dup; changed evidence digest → new
  record + prior superseded WITHIN the same lineage; independent corroborating sources coexist
  (`anchor_key` folded into `identity_key`). Proofs: `07-provenance-and-idempotency-proof.md`.

## Exposure (all read-only; one CLI writer) — `09-api-cli-mcp-exposure-proof.md`
- **API:** 6 read-only GET routes under `/api/assistant/{decisions,preferences,open-loops}[/{id}]`.
- **CLI:** `hb-assistant decision-memory preview|extract|export|list` — read-only default; `extract
  --pack-id` required, `--apply` the sole writer (N8C-8 tables only).
- **MCP:** 6 read-only remote tools gated by default-on `assistant_decision_memory_enabled()`
  (kill-switch `HB_MCP_ASSISTANT_DECISION_MEMORY=0`) over the `mode=ro&immutable=1`+`query_only=ON`
  snapshot. 12 nav + 4 pack + 4 memory + 6 decision = 26 assistant tools preserved;
  `ai_outputs_card_upsert` still the only remote write. No write/extract/apply/action tool.

## Boundary proofs — `08-review-state-and-boundary-proof.md`, `10-no-action-no-writeback-proof.md`
Advisory-only (candidate/unreviewed, no auto-accept) · no claim/memory mutation · writes confined to the
4 N8C-8 tables (preview/dry-run row-count checks) · no action/email/calendar/task/reminder/execution
path added · no raw result_json/body/prompt persisted · bounded JSON export · no vault/rendering/startup/
N8D/vector-store.

## Verification — `11-tests.md`
- New N8C-8 tests: **44 passed**.
- N8C-1→8 regression set: **324 passed, 0 failed, exit 0**.
- `scripts/test-schedule.sh -q` (migrator/schema canary for V104): **exit 0**.
- `ruff check` on in-scope changed source: **PASS**; api.py additions add zero new findings.
- CLI/API/MCP smoke on a temp migrated DB: green.

## Commit posture
**Working tree remains uncommitted.** N8C-8 commit NOT authorized — stopped before commit. No push, no
PR, no merge. Plain commit message + no AI trailer if/when a commit is later authorized.
