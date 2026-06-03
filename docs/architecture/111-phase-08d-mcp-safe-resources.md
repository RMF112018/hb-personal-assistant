# 111 — Phase 08D MCP Safe Resources (Prompt 07)

**Baseline**: Post-08D-P06 at `0564f14` (broker + nine wrappers + denied-tools enforcement). This prompt adds the read-only resource surface.

**Objective** (per prompt): Implement five safe MCP resources generated from approved workflows/read-models only.

**Evidence**:
- `docs/evidence/construction-intelligence-phase-08d-mcp-bridge/mcp-resource-contract-proof.md` + `mcp-resource-contract-proof.json`
- `docs/architecture/111-phase-08d-mcp-safe-resources.md` (this)
- `tests/test_phase_08d_mcp_resources.py`
- `src/hb_assistant/construction/second_brain/mcp/resources.py`, extended `store.py` + `proof.py`, updated `policy.py` + `__init__.py`

## Resources (`mcp/resources.py`)
Five addressable read-only URIs, each backed by an approved Prompt 05 wrapper (no new data access):

| URI | resource name | backing wrapper |
|---|---|---|
| `hb://status/system` | mcp_status_resource | mcp_status_wrapper |
| `hb://brief/today` | mcp_today_brief_resource | mcp_get_daily_brief_wrapper |
| `hb://review/load` | mcp_review_load_resource | mcp_review_load_status_wrapper |
| `hb://research/latest` | mcp_latest_research_resource | mcp_research_packet_wrapper |
| `hb://validation/latest` | mcp_latest_validation_resource | mcp_validation_status_wrapper |

`read_resource(uri, *, db_path)` returns `{uri, resource_name, source, status, provenance, content, source_count, output_classification, freshness, policy_posture}` and runs `_assert_no_raw`. `load_resources()` is fail-closed (raises on missing/empty or contract-vs-resolver drift). An unknown URI fail-closes (`resource_not_allowed`).

## Model
- **Approved-workflow-only**: resources reuse the wrappers; no raw stores, SQL, direct APIs, writeback, URLs, or determinations.
- **Bounded + freshness + policy posture**: each payload carries a `freshness` block (`generated_utc` + `basis`) and a read-only `policy_posture`.
- **No per-access receipt**: the resources contract omits one (unlike tools); `snapshot_resource_registry()` persists a metadata-only `second_brain_mcp_resource_registry_snapshots` row (count + hash, guards 0) as the audit artifact.
- **Status**: `mcp status` now reports `mcp_resources: 5`.

## Boundary
No prompts (Prompt 08), audit/permission agent (Prompt 10), CLI surface (Prompt 11), or stdio exposure. `mcp_exposure` gate stays `deferred_not_blocking`.

## Validation
compileall exit 0; `ruff check` clean; `mypy src` clean (269 files; strict); `pytest -k phase_08d` **70 passed**; `build_mcp_resources_proof()` `proof_passed=true` (5 resources; unknown fail-closed; registry snapshot guards 0); `mcp status` `mcp_resources=5`; 08A-08B / 08C / construction-agent no-writeback proofs all `proof_passed=true` (closed 08C bundle restored after). Full matrix deferred to Prompt 15.
