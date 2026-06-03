# 112 — Phase 08D MCP Reusable Prompts (Prompt 08)

**Baseline**: Post-08D-P07 at `70204bd` (broker + nine wrappers + denied tools + five resources). This prompt adds the reusable prompt-template surface.

**Objective** (per prompt): Implement reusable prompt templates that route through allowed tools and preserve advisory/source-linked/review-controlled posture.

**Evidence**:
- `docs/evidence/construction-intelligence-phase-08d-mcp-bridge/mcp-prompt-contract-proof.md` + `mcp-prompt-contract-proof.json`
- `docs/architecture/112-phase-08d-mcp-reusable-prompts.md` (this)
- `tests/test_phase_08d_mcp_prompts.py`
- `src/hb_assistant/construction/second_brain/mcp/prompts.py`, extended `store.py` + `proof.py`, updated `policy.py` + `__init__.py`

## Prompts (`mcp/prompts.py`)
Five named, parameterized templates, each routing only through allowed tools:

| Prompt | routes_through |
|---|---|
| review_today_brief | hb_get_daily_brief, hb_validation_status |
| ask_project_question | hb_query, hb_research_packet |
| prepare_for_meeting | hb_research_packet, hb_review_load_status, hb_query |
| review_memory_candidates | hb_memory_review_list, hb_memory_feedback |
| explain_review_load | hb_review_load_status, hb_validation_status |

`render_prompt(name, arguments)` substitutes args into the template body and returns `{name, description, routes_through, forbidden, arguments, posture, messages, policy_posture}`; runs `_assert_no_raw`. `load_prompts()` is fail-closed (raises on missing/empty, contract-vs-resolver drift, or any `routes_through` not ⊆ `load_allowed_tools()`). An unknown name fail-closes (`prompt_not_allowed`).

## Model
- **Templates, not executions**: prompts are static guidance; they call no tools and touch no data.
- **Route through allowed tools only**: every `routes_through` is a subset of the 9 allowed tools (enforced at load + in the proof).
- **Shared posture**: every rendered template carries "advisory, source-linked, review-controlled" + no final financial/legal/claim/entitlement/payment determinations + no raw/SQL/writeback + no raw prompt/response persistence + **no Phase 08A/08B/08C policy bypass**.
- **No per-invocation receipt**: `snapshot_prompt_registry()` persists a metadata-only `second_brain_mcp_prompt_registry_snapshots` row (count + hash, guards 0) as the audit artifact.
- **Status**: `mcp status` now reports `mcp_prompts: 5`.

## Boundary
No audit/permission agent (Prompt 10), CLI surface (Prompt 11), or stdio exposure. `mcp_exposure` gate stays `deferred_not_blocking`.

## Validation
compileall exit 0; `ruff check` clean; `mypy src` clean (270 files; strict); `pytest -k phase_08d` **77 passed**; `build_mcp_prompts_proof()` `proof_passed=true` (5 prompts route-through-allowed-only; unknown fail-closed; registry snapshot guards 0); `mcp status` `mcp_prompts=5`; 08A-08B / 08C / construction-agent no-writeback proofs all `proof_passed=true` (closed 08C bundle restored after). Full matrix deferred to Prompt 15.
