# 160 — Phase 09 Prompt 40: Consolidate Phase 09 Readiness Reporting and Update Stale Docs

**Status:** Implementation — consolidate readiness reporting into explicit categories without overstating production; update stale V38/19-table/"ships empty" language across schema, gates, CLI, 00-README, 131, runbook; create this record. Surgical; no schema bump, no contract change, no new tables, no MCP exposure.

**Schema:** V39/22 tables (already; list name PHASE_09_V38_TABLES retained for compat). **Version:** 1.5.0-phase-09-planning. **Prompt:** 40 (follows 38/159 cli-operator + 39 daily-brief; 37 reassigned to no-writeback).

**Evidence:** verification outputs under `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/validation-outputs-prompt-40/` (schema-status, corpus-balance, approved-sources, llamaindex/hybrid, review burden, 08D/MCP gates + pytest). See runbook notes.

**Builds on:** records 131 (schema contracts V38→V39), 157/159 (operator status + CLI consolidation), 145/151/00 (prior truthful posture), 148 (batch robustness), runbook `phase-09-retrieval-memory-quality-runbook.md`.

---

## 1. Context / Problem

Prior Phase 09 work (Prompts 12/38/39) established truthful LlamaIndex readiness (core vs local vs none), review cluster usefulness, daily brief exec usefulness, and operator status surfaces. However:

- `phase_09_schema.py` (and its CLI wrapper) still used V38/19-table language and required `all_rows_zero` for `overall_status == "ready"`.
- This meant that once legitimate population occurred (approved source manifests, vector index items, review burden clusters from valid apply ops), schema-status would flip to "not_ready" — even though gates/operator intent and substrate_status already treated rc>0 as pass for populated surfaces.
- Docs (00-README ledger, 131) carried stale "nineteen V38 substrate ships empty" phrasing.
- Readiness posture was not consolidated into a single, explicit, non-overstating view (safe advisory vs semantic retrieval vs vector apply vs production=false + deferred list).

The objective: make reporting truthful to the current reality (V39/22 tables, population allowed/expected for operational tables, categories surface in operator status) while preserving all guardrails (advisory/read-only/fail-closed; no overstatement of production readiness).

No changes to contracts, seeds (minor comments), schema DDL, MCP, or write paths. All surfaces remain read-only where they were.

## 2. Decision

- Decouple "structural ready" from `all_rows_zero`: schema_status `overall_ready` = (schema >=39 and all_present and all_guards); `all_rows_zero` and per-table `row_count` remain reported as diagnostics only (for proofs that want pre-pop view).
- Update schema docstring + function + CLI docstring/human text to V39/22 + "reports row counts (some legitimately populated)".
- Ensure/refresh gates comments/docstrings that structural uses present+guards (no rows_zero), substrate distinguishes populated vs advisory_empty.
- Extend `phase_09_operator_status.py` (feed from schema + gates + review + compose hybrid/llama) to surface `readiness_categories` dict with exactly 5 keys:
  - `safe_advisory_readiness`
  - `semantic_retrieval_readiness`
  - `vector_apply_readiness`
  - `production_readiness: false`
  - `deferred_limitations: list[str]`
- Update 00-README ledger paragraph + append + Prompt 40 line.
- Patch 131 (numbers 19→22, V38→V39, "ships empty" → "reports population; ... legitimately written").
- Create this 160 (Context/Decision/Design/Validation/Guardrails + mermaid + crossrefs).
- Append runbook Known deferred + V39 section notes referencing validation outputs.
- Minor seed comment update for categories + V39/22.
- No test changes required (existing asserts on `all_rows_zero` separate from `overall` continue to hold for fresh DBs; operator tests cover categories).

Decision rationale mirrors prior truthful splits (121/148/151): report what is true, fail-closed on missing pieces, explicit deferred, never claim production.

## 3. Design

### Report shape (from schema + operator)

`phase-09-schema-status --json` now:
- `"schema_ready": schema_version >= 39`
- `"overall_status": "ready" if (schema_ready and all_tables_present and all_guards_present) else "not_ready"`
- `"all_rows_zero": ...` (still present)
- `"tables": [{..., "row_count": N}, ...]` (N may be >0 for manifests etc.)
- human text updated; exit 0 on structural ready.

`phase-09-gates` structural gate: already `schema_version >=39 and all_present and all_guards` → pass (row rc used only for per-table deferral).

`phase-09-operator-status` adds/rolls up:
```json
"readiness_categories": {
  "safe_advisory_readiness": bool,   # structural (V39+schema+guards) + review advisory_allowed
  "semantic_retrieval_readiness": bool, # safe + hybrid semantic_ready (when applied)
  "vector_apply_readiness": bool,    # local embed + policy + schema (truthful blockers)
  "production_readiness": false,
  "deferred_limitations": ["external embedding providers (policy-gated)", "full synthesis determinations", "MCP dispatch of Phase 09 actions", "..."]
}
```

Computation in operator composes existing probes (`build_hybrid_status`, `build_llamaindex_config_status`, schema report, gates, review policy) — no new heavy lifting.

### Mermaid (readiness categories flow)
```mermaid
flowchart TD
  Schema[phase_09_schema_status_report<br/>V39/22 + guards + row_counts<br/>structural_ready = ver+present+guards<br/>(no longer requires all_rows_zero)] --> Gates[phase_09_gates<br/>structural pass if present+guards<br/>per-surface: rc>0 ? pass : deferred SUBSTRATE_EMPTY<br/>substrate_status: advisory_empty | populated]
  Gates --> Operator[phase_09_operator_status<br/>rolls schema + gates + contracts<br/>+ review advisory_allowed<br/>+ compose hybrid semantic_ready<br/>+ llama local etc]
  Operator --> Categories[readiness_categories:<br/>safe_advisory_readiness (structural + advisory gates)<br/>semantic_retrieval_readiness (safe + hybrid.semantic_ready + applied)<br/>vector_apply_readiness (local embed + policy + schema)<br/>production_readiness: false<br/>deferred_limitations: [list]]
  Categories --> CLI[status CLIs + proofs report categories honestly]
  CLI --> Evidence[validation outputs + runbook notes]
```

See plan attached to Prompt 40 execution for full mermaid source.

### Files changed (surgical)
- `src/hb_assistant/construction/second_brain/phase_09_schema.py` (docstring V39/22, >=39, overall without all_rows_zero, comments)
- `src/hb_assistant/cli/second_brain.py` (phase-09-schema-status docstring + human text)
- `src/hb_assistant/construction/second_brain/phase_09_gates.py` (docstrings/comments refreshed; logic already correct)
- `src/hb_assistant/construction/second_brain/phase_09_operator_status.py` (readiness_categories + computation + doc/seed)
- `resources/config/phase_09_operator_status.seed.yaml` (minor comment)
- `docs/architecture/00-README.md` (ledger update + Prompt 40)
- `docs/architecture/131-....md` (patch numbers/text)
- `docs/architecture/160-....md` (this file)
- `docs/runbooks/phase-09-retrieval-memory-quality-runbook.md` (Known deferred + V39 notes)
- (implicit) evidence dir populated by verification run

No change to: contracts json (already table_count:22), hybrid/llamaindex (keep their detailed probes), tests (asserts stable), MCP surfaces, write paths.

## 4. Validation matrix (executed post-edits)

- `python -m pip install -e ".[dev]"`
- `.venv/bin/ruff check . && .venv/bin/ruff format . --check`
- `.venv/bin/mypy src/hb_assistant/construction/second_brain/phase_09_schema.py src/hb_assistant/construction/second_brain/phase_09_gates.py src/hb_assistant/construction/second_brain/phase_09_operator_status.py src/hb_assistant/cli/second_brain.py`
- `.venv/bin/python -m compileall -q src/hb_assistant/construction/second_brain/phase_09_schema.py ... tests/test_phase_09_schema_status.py`
- `.venv/bin/hb-assistant second-brain data-quality phase-09-schema-status --json` (ready with rows>0 after prior applies; all_rows_zero reported separately; exit 0)
- `.venv/bin/hb-assistant second-brain data-quality corpus-balance --json`
- `.venv/bin/hb-assistant second-brain retrieval approved-sources build --dry-run --json` ; proof if relevant
- `.venv/bin/hb-assistant second-brain retrieval llamaindex status --json`
- `.venv/bin/hb-assistant second-brain retrieval hybrid status --json`
- `.venv/bin/hb-assistant second-brain review burden --json` ; clusters --json ; policy-status --json
- `.venv/bin/hb-assistant second-brain data-quality phase-09-gates --json` ; phase-09-gates-proof --no-evidence --json
- 08D/MCP gates: `second-brain mcp no-writeback` ; `mcp no-raw` ; `construction-agent validate --json` ; `data-quality 08d-*-proof` etc as applicable
- `pytest tests/test_phase_09_schema_status.py tests/test_phase_09_operator_status.py -q --tb=line` (and any gates schema test)
- `pytest -m "not live and not integration and not manual" -q --tb=no -k "phase_09_schema or operator or gates"` (safe subset)
- (Optional) full safe pytest subset

**Confirmation via outputs:** schema-status overall ready (even post-populate), all_rows_zero=False ok, no "not_ready" flip from valid writes; operator reports the 5 categories with production=false + deferred list; no overstatement language; validation CLIs green where expected; no MCP.

Post-verify: arch updates (160 + 00 + 131 + runbook) + traditional commit (only summary+desc emitted).

## 5. Guardrails (enforced)

- Advisory/read-only/fail-closed: all status reports, gates, operator; no writes; proofs metadata.
- No overstatement: `production_readiness=false`; `safe_advisory` only when structural+advisory gates; semantic/vector gated on SDK+applied; explicit deferred list.
- Schema V39/22 additive preserved (list name PHASE_09_V38_TABLES for compat); guards 23 CHECK=0 on all; table-inventory count updated in docs.
- `all_rows_zero` still reported (for proofs that want empty substrate view); population now allowed for valid ops (manifests/vector/review) without flipping schema/gate ready.
- Source-linked, no raw, no external writeback, review burden two-step advisory preserved.
- Base install clean; optional extras for semantic/vector apply (truthful blockers as before).
- Tests/docs + evidence authoritative; repo truth over notes.
- Post-change: arch + verify + traditional commit (only summary+desc at end).

## 6. Cross-References

- 131 (original schema contract; numbers/text patched here)
- 157/159 (operator + CLI consolidation; categories extension)
- 00-README (ledger + Prompt 40 append)
- runbook `phase-09-retrieval-memory-quality-runbook.md` (Known deferred + V39)
- 145/151/148/121 (modeling truthful posture / batch / review)
- 133/134/138/139/120 (related Phase 09 surfaces)
- Evidence dir + validation-outputs-prompt-40/
- Package manifest v1.5.0-phase-09-planning

All requirements met. No drift on prior guardrails (LlamaIndex truthful, daily brief usefulness, review clusters, no-writeback, MCP isolation).

---

**Prompt 40 execution note (surgical doc+report consolidation only):** Core changes limited to schema logic/doc, CLI text, gates comments, operator categories, docs. Verification per exact list in plan. Traditional commit title per plan; only summary+body output at end. No edit to attached plan file. All todos tracked via TodoWrite; forbidden files (test_phase_09_memory_loader.py, phase_09_embedding_vector_policy_contract.json, obsidian-linkage-proof.json) not re-read.
