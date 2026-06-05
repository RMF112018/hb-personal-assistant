# 121 — Phase 09 Prompt 01: Phase 08D Closeout Gap Verification

**Status:** Preflight remediation (Prompt 01 — verify + resolve/classify).
**Schema:** V37 (unchanged — no migration).
**Runtime package version:** `1.3.0` (unchanged).
**HEAD:** `23e6d870b8033fcea8bf4bacc167f8d2f6c29790` (`main`).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/01-08d-gap-preflight-remediation.md` (+ `.json`, `validation-outputs-prompt-01/`).
**Builds on:** `docs/architecture/120-phase-09-retrieval-memory-quality-repo-truth-rebaseline.md` (Prompt 00).

---

## 1. Purpose

Verify that Phase 08D's local MCP bridge — runtime, receipts, gates, no-raw, no-writeback, config, and
evidence — actually holds against current repo truth before Phase 09 retrieval work, and **resolve or
classify** the closeout gaps. Preflight boundary unchanged: **no LlamaIndex / embeddings / vector /
semantic-retrieval code.** The only code change is a test-hygiene fix (tests only).

## 2. 08D closeout verification matrix (live, this run)

| Dimension | Verdict (HEAD `23e6d87`) | Source |
|---|---|---|
| MCP runtime | `mcp status`: `ready_to_serve=true`, `serve_blockers=[]`, `mcp_sdk_available=true`, `foundation_ok=true`; 9 tools / 27 denied actions / 5 resources / 5 prompts; stdio-only | `second-brain mcp status --json` |
| Receipts (substrate) | both V37 receipt tables present with 20 guard `CHECK(… = 0)` columns each | `store/migrator.py` (V37); `table-inventory` |
| Receipts (operator-DB runtime) | **0 tool-call / 0 denial receipts** in the operator DB → **gap G-02** (carried to Prompt 04) | read-only count of `~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite` |
| Gates | `phase-08d-gates` **14 pass / 0 fail / 0 deferred**, `readiness_overstated=false`, `ready_to_serve=true` | `second-brain data-quality phase-08d-gates --json` |
| No-raw | `mcp no-raw-access` `proof_passed=true` (7 surfaces) | `second-brain mcp no-raw-access --json` |
| No-writeback | `mcp no-writeback` `proof_passed=true` (7 surfaces) | `second-brain mcp no-writeback --json` |
| Config | `config-preview` preview-only (`auto_apply=false`); emits command/args + env **key names** only — no env values, secrets, tokens, or broad paths; `_assert_no_raw` enforced pre-write | `mcp/config_preview.py` |
| Evidence bundle | 08D bundle complete (gates / no-raw / no-writeback / operational-serve / config-preview / validation-matrix + supporting proofs) and internally consistent | `docs/evidence/construction-intelligence-phase-08d-mcp-bridge/` |

## 3. Central gap resolved — SDK-presence test inconsistency

**Gap.** Four tests asserted the **SDK-absent** posture unconditionally:
`tests/test_phase_08d_no_raw_access.py` and `tests/test_phase_08d_no_writeback.py` —
`assert status["ready_to_serve"] is False` and `serve_blockers == ["mcp_sdk_not_installed"]`. These were
written in Prompt 13/14 (`033ec76`), before Prompt 15 (`23e6d87`) installed the optional `mcp` SDK and
made `ready_to_serve` truthful (`policy.py:188,213-215` — `find_spec("mcp")` →
`ready_to_serve = foundation_ok and not serve_blockers`). With the `[mcp]` extra installed (this venv,
`mcp 1.27.2`), the assertions inverted → 4 failures.

**Resolution (tests only).** The four tests now assert SDK-state-aware: the substantive Prompt-13/14
guarantee is kept (`no_raw_access_proof`/`no_writeback_proof` are `pass`; the pending blockers are absent
from `serve_blockers`), and the readiness assertion branches on `importlib.util.find_spec("mcp")` —
SDK present → `ready_to_serve=True` / `serve_blockers=[]`; absent → `False` /
`["mcp_sdk_not_installed"]`. This strengthens the tests (covers **both** branches), preserves intent,
and makes the suite green in either environment. No runtime/policy/schema change.

## 4. Carry-forward classifications

- **G-02 (MCP runtime receipt population = 0 in operator DB)** — substrate + operational stdio serve
  proof (separate proof DB, 1 allow + 1 deny) verified; operator-DB allowed/denied receipt smoke is owned
  by **Prompt 04** (`Prompt_04_MCP_Runtime_Receipt_And_Denial_Smoke_Preflight`). Non-blocking for this
  prompt; a Phase-09 blocker tracked by Prompt 04.
- **08C forecast-readiness warning** — 1 non-blocking gate (external Procore dependency), preserved.
- Generated-output / memory / automation / Obsidian / corpus gaps (G-01, G-03…G-08, G-10) — owned by
  preflight Prompts 03, 05–11 (see record 120).

## 5. Guardrails & stop conditions

Local-first, read-only; no Graph/Procore/email/calendar/source-system/external writeback; no raw content,
tokens, signed/download URLs, or PEMs; no raw vector search via MCP; advisory only. No stop condition
triggered — the 0-receipt operator DB and the (now-resolved) SDK-presence test gap are not safety
regressions; the no-raw/no-writeback proofs pass and `ready_to_serve=true` is the documented SDK-present
state.

## LlamaIndex readiness truthful across installs (post-Prompt 19/20 follow-up) — precedent reference

The MCP SDK-state-aware pattern and test fixes in §3 of this record (unconditional `ready_to_serve=False`
/ absent-only asserts written before the optional extra was installed → made state-aware on
`find_spec("mcp")` so both present (`True`/[]) and absent (`False`/["mcp_sdk_not_installed"]) are covered,
making the readiness flag truthful post-install) was explicitly used as the model for the Phase 09
LlamaIndex follow-up.

See the appended subsections in 132 (LlamaIndex config/status), 137 (dry-run), 138 (apply), 139 (hybrid),
and the implementation in `llamaindex_config.py` (split core/local probes + runtime_ready + blockers),
`vector_index.py` (plan fields, split apply gate, HF guard), `hybrid_broker.py` (query guard, status),
CLI updates, test monkey renames + new local-not-ready case, pyproject/runbook, and 120/131/00-README.

This preserves the "no overstatement of readiness" and "truthful final state" discipline called out in
this record and the Phase 09 rebaseline (120).
