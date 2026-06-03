# Phase 08D — Prompt 04: MCP Tool Broker Proof

**Evidence artifacts:** `mcp-tool-broker-proof.md` (this) + `mcp-tool-broker-proof.json` (generated)
**Package manifest:** `HB_Construction_Intelligence_Phase_08D_Local_MCP_Bridge_Implementation_Package/00_PACKAGE_MANIFEST.md` · `v1.4.0-phase-08d-planning`
**Run date:** 2026-06-03 · **Base HEAD:** `0498fef` · **Schema:** V37
**Scope:** Policy-gated tool broker — registry loading, deny-first dispatch, argument validation, bounded + no-raw output validation, metadata-only receipts, fail-closed errors. The nine workflow **wrappers** are Prompt 05; the broker dispatches through an injectable registry and fail-closes (`wrapper_unavailable`) until they land.

---

## 1. Posture

Local-first, read-only, no-writeback, no-raw, advisory-only posture preserved. Every
dispatch path writes a **metadata-only** receipt (hashes/counts/reason codes only) with
all twenty V37 guard columns at 0. The broker never persists or returns raw arguments,
results, prompts, responses, SQL, tokens, secrets, signed/download URLs, or
determinations, and never opens a socket (it is not yet exposed over stdio).

---

## 2. Registries (fail-closed loaders)

`mcp/registry.py` loads from the landed contracts:
- **Allowed tools: 9** — `hb_status`, `hb_query`, `hb_research_packet`, `hb_get_daily_brief`,
  `hb_open_daily_brief`, `hb_review_load_status`, `hb_memory_review_list`,
  `hb_memory_feedback`, `hb_validation_status` (each → its `mcp_*_wrapper`).
- **Denied actions: 27** — `arbitrary_sql`, `raw_file_read`, `raw_obsidian_read`,
  `raw_sqlite_query`, `graph_api_call`, `procore_api_call`, `email_send`,
  `calendar_update`, `source_system_writeback`, the six `raw_*_access` actions, the two
  `*_url_access` actions, `payment_decision`, `claim_decision`, `entitlement_decision`,
  `final_financial_determination`, `external_delivery`, `slack_send`, `teams_send`,
  `sms_send`, `push_notification_send`.

A missing/empty registry raises `RegistryUnavailable` (fail-closed).

---

## 3. Dispatch flow (`ToolBroker.dispatch`) — deny first

1. correlation_id assigned; tool name canonicalized.
2. **deny first**: tool name in the denied set, **or** any denied-action token present in
   the arguments → `action_denied_by_policy`.
3. tool not in the allowed registry → `tool_not_allowed`.
4. argument validation (dict, JSON-serializable, ≤ 16 KiB) → else `invalid_arguments`.
5. wrapper not registered → `wrapper_unavailable` (the P04 state for all nine tools).
6. wrapper raises → `broker_error` (no raw error text echoed or stored).
7. output bounded to `MAX_RESULTS=50` and run through `_assert_no_raw` → on a forbidden
   pattern → `unsafe_output`.
8. allowed → metadata-only tool-call receipt + safe envelope (`status`, `provenance`,
   `policy_posture`, `receipt_id`, bounded result).

## 4. Reason codes

`action_denied_by_policy`, `tool_not_allowed`, `wrapper_unavailable`,
`invalid_arguments`, `unsafe_output`, `broker_error`.

---

## 5. Exercised scenarios (`mcp-tool-broker-proof.json`, `proof_passed=true`)

| Scenario | Decision | Reason code | Receipt |
|---|---|---|---|
| denied action (`arbitrary_sql`) | denied | `action_denied_by_policy` | denial |
| unknown tool | denied | `tool_not_allowed` | denial |
| allowed tool, no wrapper | denied | `wrapper_unavailable` | denial |
| denied token in args | denied | `action_denied_by_policy` | denial |
| unsafe wrapper output (URL) | denied | `unsafe_output` | denial |
| allowed tool + injected wrapper | allowed | — | tool-call |

Receipt counts in the exercise: **1 tool-call, 5 denial**. The allowed→success path uses
an **injected test wrapper** (the real wrappers land in Prompt 05). DB attestations:
every guard column 0; the receipt tables have **no raw arg/result columns** (only
`args_hash`/`result_hash`).

---

## 6. Validation commands + results

| Command | Result |
|---|---|
| `python -m compileall -q src tests` | exit 0 |
| `ruff check` (mcp module + test) | All checks passed |
| `mypy src` | Success — no issues in **267** source files (module strict) |
| `pytest test_phase_08d_mcp_broker + mcp_server + schema_v37 + contracts` | **27 passed** |
| `build_mcp_tool_broker_proof()` | `proof_passed=true`; registries 9/27; receipts 1 tool-call / 5 denial |
| `second-brain mcp status --json` | `mcp_allowed_tool_specs=9`, `mcp_denied_actions=27`, `mcp_tools_registered=0`, `ready_to_serve=false` (`workflow_wrappers_not_implemented_prompt_05`) |
| `second-brain data-quality no-writeback-proof` | `proof_passed=true` |
| `second-brain data-quality phase-08c-no-writeback-proof` | `proof_passed=true` |
| `construction-agent data-quality no-writeback-proof` | `proof_passed=true` |

**Validation-subset rationale:** focused on the touched broker surface + the three
no-writeback proofs, per the validation-minimum rule. Closed-phase evidence churned by the
proof runs was restored. Full matrix at Prompt 15.

---

## 7. Deferred / scope statement

- **Workflow wrappers** → Prompt 05 (all nine allowed tools currently fail-closed with
  `wrapper_unavailable`); **resources** → Prompt 07; **prompts** → Prompt 08;
  **audit/receipt proof** → Prompt 10; **CLI dispatch surfaces** → Prompt 11;
  **MCP no-raw-access proof** → Prompt 13; **MCP no-writeback proof** → Prompt 14.
- The broker is **not yet exposed over stdio**; `serve` remains fail-closed.
- `_AGENT_GUARDRAILS["mcp_implemented"]` stays **False**; `mcp_exposure` gate
  `deferred_not_blocking`.

**Verdict:** the policy-gated broker, deny-first registries, argument/output validation,
metadata-only receipts, and fail-closed reason codes are landed and green. Cleared for
Prompt 05 (allowed workflow tools).
