# Phase 08D — Prompt 08: MCP Reusable Prompts Proof

**Evidence artifacts:** `mcp-prompt-contract-proof.md` (this) + `mcp-prompt-contract-proof.json` (generated)
**Package manifest:** `HB_Construction_Intelligence_Phase_08D_Local_MCP_Bridge_Implementation_Package/00_PACKAGE_MANIFEST.md` · `v1.4.0-phase-08d-planning`
**Run date:** 2026-06-03 · **Base HEAD:** `70204bd` · **Schema:** V37
**Scope:** Five reusable MCP prompt templates that route through allowed tools and preserve advisory/source-linked/review-controlled posture. Templates only — no tool execution, no data access; fail-closed on unknown names; the prompt-registry snapshot is the audit artifact.

---

## 1. Posture

Local-first, read-only, no-writeback, no-raw, advisory-only. Each prompt is a static
template (with argument substitution) that routes **only** through allowed tools and carries
a shared posture: *advisory, source-linked, review-controlled; no final
financial/legal/claim/entitlement/payment determinations; no raw stores/SQL/raw content; no
writeback; no raw prompt/response persistence; no Phase 08A/08B/08C policy bypass*. Rendered
templates pass `_assert_no_raw`.

---

## 2. The five prompts (route through allowed tools only)

| Prompt | routes_through (⊆ the 9 allowed tools) | forbidden |
|---|---|---|
| `review_today_brief` | hb_get_daily_brief, hb_validation_status | raw stores, final determinations, writeback |
| `ask_project_question` | hb_query, hb_research_packet | arbitrary SQL, direct APIs, unsupported conclusions |
| `prepare_for_meeting` | hb_research_packet, hb_review_load_status, hb_query | legal/claim/final decisions |
| `review_memory_candidates` | hb_memory_review_list, hb_memory_feedback | raw source replay, preference overriding safety |
| `explain_review_load` | hb_review_load_status, hb_validation_status | raw record inspection |

`render_prompt(name, arguments)` returns
`{name, description, routes_through, forbidden, arguments, posture, messages:[{role,content}],
policy_posture}` with args substituted; an unknown name fail-closes
(`status=denied`, `reason_code=prompt_not_allowed`, `fail_closed=true`).

## 3. Contract requirements satisfied

`route_through_allowed_tools` (every `routes_through` ⊆ the allowed registry) ·
`no_raw_store_instructions` · `no_writeback_instructions` ·
`no_final_financial_legal_claim_entitlement_payment_determinations` ·
`no_raw_prompt_response_persistence`. Plus the standing **no Phase 08A/08B/08C policy
bypass** guidance in every rendered template.

## 4. Registry snapshot

`snapshot_prompt_registry()` persists a metadata-only
`second_brain_mcp_prompt_registry_snapshots` row (`prompt_count=5`, `registry_hash`,
policy/schema version) with all twenty guard columns 0. (No per-invocation receipts —
templates, like resources, omit them.)

---

## 5. Proof results (`mcp-prompt-contract-proof.json`, `proof_passed=true`)

- All five prompts render with `routes_through` ⊆ allowed tools, the posture markers
  (advisory / source-linked / review-controlled) + the no-determination + no-policy-bypass
  language, and **no forbidden result fields** (recursive exact-key scan).
- An unknown prompt name **fail-closes** (`prompt_not_allowed`).
- The prompt-registry snapshot persists guard-clean (`prompt_count=5`).
- `_assert_no_raw` clean over the whole proof.

---

## 6. Validation commands + results

| Command | Result |
|---|---|
| `python -m compileall -q src tests` | exit 0 |
| `ruff check` (mcp module + test) | All checks passed |
| `mypy src` | Success — no issues in **270** source files (strict) |
| `pytest -k phase_08d` | **77 passed** |
| `build_mcp_prompts_proof()` | `proof_passed=true`; 5 prompts; unknown fail-closed; snapshot guards 0 |
| `second-brain mcp status --json` | `mcp_prompts=5` (tools 9 / resources 5 / denied 27) |
| `second-brain data-quality no-writeback-proof` | `proof_passed=true` |
| `second-brain data-quality phase-08c-no-writeback-proof` | `proof_passed=true` |
| `construction-agent data-quality no-writeback-proof` | `proof_passed=true` |

**Validation-subset rationale:** focused on the prompt surface + the full 08D suite + the
three no-writeback proofs, per the validation-minimum rule. Closed-phase evidence churned by
the proof runs was restored. Full matrix at Prompt 15.

---

## 7. Deferred / scope statement

- **Audit/permission agent + registry snapshots orchestration**: Prompt 10; **CLI surfaces**
  (`mcp prompts`): Prompt 11; **MCP data-quality gates**: Prompt 12; **MCP no-raw-access /
  no-writeback proofs**: Prompts 13/14.
- Prompts are not yet exposed over stdio (`serve` fail-closed). `mcp_implemented` stays
  False; `mcp_exposure` gate `deferred_not_blocking`.

**Verdict:** the five reusable prompts route through allowed tools only, preserve the
advisory/source-linked/review-controlled posture, forbid determinations + policy bypass, and
are green. Cleared for Prompt 09 (Claude Desktop config + runbook).
