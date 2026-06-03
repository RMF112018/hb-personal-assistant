# Phase 08D — Prompt 07: MCP Safe Resources Proof

**Evidence artifacts:** `mcp-resource-contract-proof.md` (this) + `mcp-resource-contract-proof.json` (generated)
**Package manifest:** `HB_Construction_Intelligence_Phase_08D_Local_MCP_Bridge_Implementation_Package/00_PACKAGE_MANIFEST.md` · `v1.4.0-phase-08d-planning`
**Run date:** 2026-06-03 · **Base HEAD:** `0564f14` · **Schema:** V37
**Scope:** Five safe MCP resources generated from approved workflows/read-models only. Read-only, bounded, fail-closed; reads emit no per-access receipt (contract omits one) and a resource-registry snapshot is the audit artifact.

---

## 1. Posture

Local-first, read-only, no-writeback, no-raw, advisory-only. Each resource is generated
from a Prompt 05 wrapper (an approved read-model) — no new data access. Payloads are
bounded, carry freshness + policy posture, and pass `_assert_no_raw`. Nothing exposes raw
SQLite, arbitrary SQL, raw files/Obsidian, direct Graph/Procore, writeback, raw payloads,
signed/download URLs, raw prompts/responses, or determinations.

---

## 2. The five resources (approved-workflow-sourced)

| URI | resource name | backing read-model (Prompt 05 wrapper) |
|---|---|---|
| `hb://status/system` | `mcp_status_resource` | `mcp_status_wrapper` (safe status workflow) |
| `hb://brief/today` | `mcp_today_brief_resource` | `mcp_get_daily_brief_wrapper` (daily brief render view) |
| `hb://review/load` | `mcp_review_load_resource` | `mcp_review_load_status_wrapper` (review triage/load) |
| `hb://research/latest` | `mcp_latest_research_resource` | `mcp_research_packet_wrapper` (latest research packet) |
| `hb://validation/latest` | `mcp_latest_validation_resource` | `mcp_validation_status_wrapper` (gates/no-writeback summaries) |

Each `read_resource(uri)` returns
`{uri, resource_name, source, status, provenance, content(bounded), source_count,
output_classification, freshness:{generated_utc, basis:"computed_live"}, policy_posture}`.

## 3. Contract requirements satisfied

`approved_workflow_source` (wrappers only) · `bounded_structured_output` · `freshness_metadata`
(every resource carries a `freshness` block) · `policy_posture` (read-only / no-writeback /
no-raw / no-final-determination) · `fail_closed` (an unknown URI →
`status=denied`, `reason_code=resource_not_allowed`, `fail_closed=true`).

## 4. Registry snapshot

`snapshot_resource_registry()` persists a metadata-only
`second_brain_mcp_resource_registry_snapshots` row (`resource_count=5`, `registry_hash`,
policy/schema version) with all twenty guard columns 0. (Per-access receipts are
intentionally omitted — the resources contract does not require one; the registry snapshot
is the audit artifact.)

---

## 5. Proof results (`mcp-resource-contract-proof.json`, `proof_passed=true`)

- All five resources resolve to an approved-workflow-sourced, bounded payload with
  `freshness` + `policy_posture` and **no forbidden result fields** (recursive exact-key
  scan).
- An unknown URI (`hb://secrets/all`) **fail-closes** (`resource_not_allowed`).
- The resource-registry snapshot persists guard-clean (`resource_count=5`).
- `_assert_no_raw` clean over the whole proof.

---

## 6. Validation commands + results

| Command | Result |
|---|---|
| `python -m compileall -q src tests` | exit 0 |
| `ruff check` (mcp module + test) | All checks passed |
| `mypy src` | Success — no issues in **269** source files (strict) |
| `pytest -k phase_08d` | **70 passed** |
| `build_mcp_resources_proof()` | `proof_passed=true`; 5 resources; unknown fail-closed; snapshot guards 0 |
| `second-brain mcp status --json` | `mcp_resources=5` (tools 9 / denied 27) |
| `second-brain data-quality no-writeback-proof` | `proof_passed=true` |
| `second-brain data-quality phase-08c-no-writeback-proof` | `proof_passed=true` |
| `construction-agent data-quality no-writeback-proof` | `proof_passed=true` |

**Validation-subset rationale:** focused on the resource surface + the full 08D suite + the
three no-writeback proofs, per the validation-minimum rule. Closed-phase evidence churned by
the proof runs was restored. Full matrix at Prompt 15.

---

## 7. Deferred / scope statement

- **Prompts**: Prompt 08; **audit/permission agent + registry snapshots orchestration**:
  Prompt 10; **CLI surfaces** (`mcp resources`): Prompt 11; **MCP no-raw-access /
  no-writeback proofs**: Prompts 13/14.
- Resources are not yet exposed over stdio (`serve` fail-closed). `mcp_implemented` stays
  False; `mcp_exposure` gate `deferred_not_blocking`.

**Verdict:** the five safe resources are approved-workflow-sourced, bounded, read-only,
fail-closed, and green. Cleared for Prompt 08 (reusable prompts).
