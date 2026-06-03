# Phase 08D — Prompt 05: MCP Allowed Workflow Tools Proof

**Evidence artifacts:** `mcp-workflow-wrapper-proof.md` (this) + `mcp-tool-contract-proof.json` (generated)
**Package manifest:** `HB_Construction_Intelligence_Phase_08D_Local_MCP_Bridge_Implementation_Package/00_PACKAGE_MANIFEST.md` · `v1.4.0-phase-08d-planning`
**Run date:** 2026-06-03 · **Base HEAD:** `a5cf1c4` · **Schema:** V37
**Scope:** The nine `mcp_*_wrapper` functions as **workflow wrappers only** over existing offline-safe, metadata-only builders. No raw stores, arbitrary SQL, direct APIs, or writeback. The broker can now dispatch real tools in-process; stdio serving stays fail-closed on the Prompt 13/14 guard proofs.

---

## 1. Posture

Local-first, read-only, no-writeback (external), no-raw, advisory-only. Each wrapper calls
an existing builder **offline** (mock-first synthesis; `emit_receipt=False`) and returns a
**bounded summary** of safe scalar/count/class fields only — never raw bodies, prompts,
responses, SQL, tokens, signed/download URLs, or final determinations. The broker adds
`policy_posture` + `receipt_id`, bounds the output, and runs `_assert_no_raw`. The only
local write is `hb_memory_feedback`, which records a local feedback-log row (local
metadata; no external/source-system writeback).

---

## 2. The nine wrappers → reused builders

| Tool | Reused builder(s) | Bounded fields returned |
|---|---|---|
| hb_status | `load_second_brain_config` + `build_agent_registry_proof` + `run_automation_health` | runtime_mode, config_status, agent counts, automation status/reason |
| hb_validation_status | `evaluate_phase_08a/08b/08c_data_quality_gates` + `build_second_brain_no_writeback_proof` + `build_mcp_tool_broker_proof` | per-phase gate ok, readiness_overstated, proof_passed flags (08D gates pending Prompt 12) |
| hb_query | `synthesize_answer` (mock-first) | synthesized, answer_redacted, source_ref_count, context_quality_class, degradation_mode, review_tier, warnings |
| hb_research_packet | `RetrievalOrchestrator.orchestrate` | context_quality_class, degradation_mode, source/review counts, families present/missing, source_coverage, open_questions(codes) |
| hb_get_daily_brief | `evaluate_daily_brief_delivery` | overall_status, reason_code, brief_date, eligible, already_delivered, delivery_channel |
| hb_open_daily_brief | `evaluate_brief_open` (read-only) | reason_code, policy_open_enabled, eligible, already_opened, **opened=False**, path_hash |
| hb_review_load_status | `ReviewTriageAgent.summarize` + `evaluate_source_freshness` | total/tier_3/mandatory counts, by_tier, by_urgency, freshness status, stale/unknown counts |
| hb_memory_review_list | `read_memory_candidates(status="proposed")` | candidate_id, type, confidence_class, review_tier, sensitivity_class, status (no bodies) |
| hb_memory_feedback | `record_operator_feedback(emit=True)` | feedback_id, target_kind/id, feedback_class, recorded=True (local feedback log only) |

Wrappers **degrade gracefully** (never raise) on empty/insufficient local state; an empty
DB yields safe `degraded`/`ok` summaries, not errors.

---

## 3. Contract proof (`mcp-tool-contract-proof.json`, `proof_passed=true`)

All nine tools dispatched through the **real broker** (`build_default_broker`) against a
fresh temp DB:
- every tool `decision=allowed` with a complete envelope (`status`, `provenance`,
  `policy_posture`, `receipt_id`) and a bounded result;
- **9 metadata-only tool-call receipts** written, all twenty guard columns 0;
- **no forbidden result fields** (recursive exact-key scan over the envelope:
  raw_body/prompt/response/sql/source_content, signed_url, download_url, token, secret,
  final_determination — none present);
- `_assert_no_raw` clean over the whole proof.

---

## 4. Validation commands + results

| Command | Result |
|---|---|
| `python -m compileall -q src tests` | exit 0 |
| `ruff check` (mcp module + tests) | All checks passed |
| `mypy src` | Success — no issues in **268** source files (strict) |
| `pytest test_phase_08d_mcp_wrappers + broker + server + contracts + schema_v37` | **34 passed** |
| `build_mcp_allowed_tools_proof()` | `proof_passed=true`; 9 tools allowed; 9 receipts; guards 0; no forbidden fields |
| `second-brain mcp status --json` | `mcp_tools_registered=9`, `ready_to_serve=false` (guard-proof + SDK blockers only) |
| `second-brain data-quality no-writeback-proof` | `proof_passed=true` |
| `second-brain data-quality phase-08c-no-writeback-proof` | `proof_passed=true` |
| `construction-agent data-quality no-writeback-proof` | `proof_passed=true` |

**Validation-subset rationale:** focused on the touched wrapper surface + the three
no-writeback proofs, per the validation-minimum rule. Closed-phase evidence churned by the
proof runs was restored. Full matrix at Prompt 15.

---

## 5. Deferred / scope statement

- **CLI dispatch surfaces** (`mcp tools`/`call`) → Prompt 11; **resources** → Prompt 07;
  **prompts** → Prompt 08; **audit/permission agent** → Prompt 10;
  **MCP data-quality gates** → Prompt 12; **MCP no-raw-access proof** → Prompt 13;
  **MCP no-writeback proof** → Prompt 14.
- The broker + wrappers are **not yet exposed over stdio**; `serve` stays fail-closed on
  the two guard proofs (and the optional SDK). `mcp_implemented` stays **False**;
  `mcp_exposure` gate `deferred_not_blocking`.
- `hb_memory_feedback` writes only a local `second_brain_operator_feedback` row (per the
  approved decision) — no candidate promotion, no external writeback.

**Verdict:** the nine allowed workflow wrappers are workflow-only, offline-safe, bounded,
metadata-only, and green. Cleared for Prompt 06 (denied tools + policy enforcement).
