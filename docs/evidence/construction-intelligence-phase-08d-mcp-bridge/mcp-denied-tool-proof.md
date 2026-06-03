# Phase 08D — Prompt 06: MCP Denied Tools and Policy Enforcement Proof

**Evidence artifacts:** `mcp-denied-tool-proof.md` (this) + `mcp-denied-tool-proof.json` (generated)
**Package manifest:** `HB_Construction_Intelligence_Phase_08D_Local_MCP_Bridge_Implementation_Package/00_PACKAGE_MANIFEST.md` · `v1.4.0-phase-08d-planning`
**Run date:** 2026-06-03 · **Base HEAD:** `8cd0800` · **Schema:** V37
**Scope:** Explicit denied actions + metadata-only denial receipts + tests for each denial class. Deny-first enforcement (broker, Prompt 04) is now proven across all 27 actions, with denial receipts that never echo raw requested content.

---

## 1. Posture

Local-first, read-only, no-writeback, no-raw, advisory-only. Every denied request produces
a **metadata-only** denial receipt (`requested_action`, `denial_reason_code`,
`request_hash`, policy/schema version, correlation id) with all twenty guard columns 0. The
`second_brain_mcp_denial_receipts` table has **no raw/content columns** — raw arguments are
reduced to a `request_hash` and never persisted.

---

## 2. The 27 denied actions (deny-first; flat registry)

Enforced from `phase_08d_mcp_denied_tools_contract.json`. Grouped below into conceptual
classes for readability (enforcement is the flat list; reason code is the single
`action_denied_by_policy`, with `requested_action` naming the specific action):

| Class | Denied actions |
|---|---|
| arbitrary_sql | `arbitrary_sql`, `raw_sqlite_query` |
| raw_store | `raw_file_read`, `raw_obsidian_read` |
| direct_api | `graph_api_call`, `procore_api_call` |
| source_writeback | `email_send`, `calendar_update`, `source_system_writeback` |
| raw_payload | `raw_email_body_access`, `raw_document_text_access`, `raw_calendar_payload_access`, `raw_procore_payload_access`, `raw_financial_payload_access`, `raw_prompt_access`, `raw_response_access` |
| url | `signed_url_access`, `download_url_access` |
| determination | `payment_decision`, `claim_decision`, `entitlement_decision`, `final_financial_determination` |
| external_delivery | `external_delivery`, `slack_send`, `teams_send`, `sms_send`, `push_notification_send` |

## 3. Enforcement model

- **Deny first**: the denied registry is checked before the allowed registry and before any
  argument validation or wrapper dispatch.
- **By name or by token**: a request whose *tool name* is a denied action is denied; a
  denied action riding inside an *allowed* tool's arguments is also denied. The denial
  receipt names the **specific denied action** (the tool name, or the matched token).
- **Single reason code**: `action_denied_by_policy` (the package prescribes one code; the
  `requested_action` field carries the specific action — no per-class enumeration).
- No separate `allow_*` permission layer — deny-first plus the allowed registry is the gate.

---

## 4. Proof results (`mcp-denied-tool-proof.json`, `proof_passed=true`)

- **All 27 denied actions** → `decision=denied`, `reason_code=action_denied_by_policy`,
  `requested_action` == the action, denial `receipt_id` present.
- **Denied token in args** (`hb_status` + `{"mode":"graph_api_call"}`) → denied,
  `requested_action=graph_api_call`.
- **Raw-content-not-persisted**: a denied request carrying a secret marker + a fake URL in
  arguments → neither the marker nor the URL appears in **any** denial-receipt column
  (only the `request_hash` is stored).
- **Metadata-only**: the denial table has no raw columns; all twenty guard columns 0.
- **29 denial receipts** written in the exercise (27 actions + the token case + the
  raw-content case).

---

## 5. Validation commands + results

| Command | Result |
|---|---|
| `python -m compileall -q src tests` | exit 0 |
| `ruff check` (broker + proof + test) | All checks passed |
| `mypy src` | Success — no issues in **268** source files (strict) |
| `pytest test_phase_08d_mcp_denied + broker + wrappers` | **48 passed** (incl. 27 parametrized denial cases) |
| `build_mcp_denied_tools_proof()` | `proof_passed=true`; 27 actions; 29 receipts; no raw echoed; guards 0 |
| `second-brain data-quality no-writeback-proof` | `proof_passed=true` |
| `second-brain data-quality phase-08c-no-writeback-proof` | `proof_passed=true` |
| `construction-agent data-quality no-writeback-proof` | `proof_passed=true` |

**Validation-subset rationale:** focused on the denial surface + the three no-writeback
proofs, per the validation-minimum rule. Closed-phase evidence churned by the proof runs was
restored. Full matrix at Prompt 15.

---

## 6. Deferred / scope statement

- No named denial classes / per-action reason-code enumeration (package: flat list, single
  reason code). No `allow_*` permission layer. No CLI surface (Prompt 11); broker not yet
  exposed over stdio (`serve` fail-closed). MCP no-raw-access / no-writeback proofs are
  Prompts 13/14; `mcp_implemented` stays False (`mcp_exposure` gate `deferred_not_blocking`).

**Verdict:** all 27 denied actions are explicitly enforced deny-first with metadata-only,
no-raw-echo denial receipts. Cleared for Prompt 07 (safe resources).
