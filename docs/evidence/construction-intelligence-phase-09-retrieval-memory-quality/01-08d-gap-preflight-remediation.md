# Phase 09 — Prompt 01: 08D Closeout Gap Verification

**Evidence artifact:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/01-08d-gap-preflight-remediation.md`
**Machine-readable companion:** `01-08d-gap-preflight-remediation.json`
**Captured outputs:** `validation-outputs-prompt-01/`
**Package manifest:** `HB_Construction_Intelligence_Phase_09_Retrieval_Memory_Quality_Implementation_Package/00_PACKAGE_MANIFEST.md` (planning label `v1.4.0-phase-09-planning`; package version `1.3.0`)
**Audit date:** 2026-06-04
**Posture:** Verify Phase 08D closeout against current repo truth; **resolve or classify** the gaps. The only code change is a **tests-only** hygiene fix; **no runtime, schema, or `pyproject` change, and no LlamaIndex/embeddings/vector/semantic-retrieval code** (the explicit preflight boundary). The historical 08D evidence bundle is not rewritten.

---

## 1. Scope & guardrail posture

This prompt verifies that Phase 08D's local MCP bridge — **runtime, receipts, gates, no-raw,
no-writeback, config, and evidence** — holds against `main` at HEAD `23e6d87` (schema **V37**, version
**1.3.0**), and resolves/classifies the closeout gaps before Phase 09 retrieval work. Repository truth is
authoritative. Local-first, read-only, no-writeback, no-raw, advisory-only posture preserved unchanged.
Nothing here persists raw content, performs writeback, exposes raw stores / arbitrary SQL / a raw vector
index, or makes a final determination.

---

## 2. 08D closeout verification matrix (live, HEAD `23e6d87`)

| Dimension | Verdict | Source |
|---|---|---|
| **MCP runtime** | `ready_to_serve=true`, `serve_blockers=[]`, `mcp_sdk_available=true`, `foundation_ok=true`; 9 tools / 27 denied actions / 5 resources / 5 prompts; stdio-only | `second-brain mcp status --json` |
| **Receipts (substrate)** | both V37 receipt tables present (`second_brain_mcp_tool_call_receipts`, `second_brain_mcp_denial_receipts`), 20 guard `CHECK(… = 0)` columns each | `store/migrator.py` (V37); `table-inventory` (schema 37, 0 unmapped) |
| **Receipts (operator-DB runtime)** | **0 tool-call / 0 denial receipts** → gap **G-02** (see §4) | read-only count of the operator DB |
| **Gates** | `phase-08d-gates` **14 pass / 0 warning / 0 fail / 0 deferred**, `ready_to_serve=true`, `readiness_overstated=false` | `second-brain data-quality phase-08d-gates --json` |
| **No-raw** | `mcp no-raw-access` `proof_passed=true` (7 surfaces) | `second-brain mcp no-raw-access --json` |
| **No-writeback** | `mcp no-writeback` `proof_passed=true` (7 surfaces) | `second-brain mcp no-writeback --json` |
| **Config** | `config-preview` preview-only (`auto_apply=false`); emits command/args + env **key names** only — no env values, secrets, tokens, or broad paths; `_assert_no_raw` enforced pre-write | `mcp/config_preview.py` |
| **Evidence bundle** | 08D bundle complete (gates / no-raw / no-writeback / operational-serve / config-preview / validation-matrix + supporting proofs) and internally consistent | `docs/evidence/construction-intelligence-phase-08d-mcp-bridge/` |

All seven verifiable dimensions hold. The one gap (operator-DB receipt population) is classified in §4.

---

## 3. Central gap **resolved** — SDK-presence test inconsistency

**Before.** Four tests asserted the **SDK-absent** posture unconditionally:

```
tests/test_phase_08d_no_raw_access.py::test_startup_check_passes_and_drops_prompt_13_blocker
tests/test_phase_08d_no_raw_access.py::test_data_quality_gate_no_raw_access_now_passes
tests/test_phase_08d_no_writeback.py::test_startup_check_passes_and_drops_prompt_14_blocker
tests/test_phase_08d_no_writeback.py::test_data_quality_gate_no_writeback_now_passes
```

Each hard-asserted `ready_to_serve is False` and `serve_blockers == ["mcp_sdk_not_installed"]`. Written in
Prompt 13/14 (`033ec76`) before Prompt 15 (`23e6d87`) installed the optional `mcp` SDK and made
`ready_to_serve` truthful (`policy.py:188,213-215` — `mcp_sdk_available = find_spec("mcp") is not None`;
`ready_to_serve = foundation_ok and not serve_blockers`). With the `[mcp]` extra installed in this venv
(`mcp 1.27.2`), the assertions inverted → **4 failures** at Prompt 00 (`3012 passed / 4 failed`).

**After (resolution, tests only).** The four tests now assert SDK-state-aware. The substantive
Prompt-13/14 guarantee is kept (`no_raw_access_proof` / `no_writeback_proof` are `pass`; the pending
blockers are absent from `serve_blockers`); the readiness assertion branches on
`importlib.util.find_spec("mcp")`:

```python
if importlib.util.find_spec("mcp") is not None:   # SDK present (this venv)
    assert status["serve_blockers"] == []
    assert status["ready_to_serve"] is True
else:                                              # SDK absent → fail-closed
    assert status["serve_blockers"] == ["mcp_sdk_not_installed"]
    assert status["ready_to_serve"] is False
```

This **strengthens** the tests (covers both SDK branches), preserves intent, and makes the suite green in
either environment. No runtime/policy/schema change; the edit touches only the two test files.

**Result:** `pytest -m "not live and not integration and not manual"` → **3016 passed / 0 failed /
0 skipped** (exit 0). The 16 tests in the two edited files pass; the four prior failures are resolved.

---

## 4. Receipts gap **classified** — G-02 (operator-DB runtime population)

Read-only count of the operator DB
`~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`:

```
second_brain_mcp_tool_call_receipts = 0
second_brain_mcp_denial_receipts    = 0
```

The receipt **substrate** (two V37 tables, 20 guard `CHECK(… = 0)` columns each) and the **operational
stdio serve proof** (a separate proof DB with 1 allowed + 1 denied receipt, guard columns held) are
verified. What is absent is **operator-DB runtime population** — gap **G-02**. Per the package gap
register, operator-DB allowed/denied receipt-and-denial smoke is owned by
**`Prompt_04_MCP_Runtime_Receipt_And_Denial_Smoke_Preflight`**. This prompt verifies the substrate and
proof and **carries G-02 forward**; it does not populate the operator DB (and must not — population
belongs to a controlled smoke run, not a verification pass).

---

## 5. Validation commands & results (HEAD `23e6d87`, `.venv/bin/python3.12`)

Captured under `validation-outputs-prompt-01/`.

| Command (as run) | Exit | Result |
|---|---|---|
| `python -m compileall -q src tests` | 0 | ok |
| `ruff check .` | 0 | All checks passed! |
| `mypy src` | 0 | Success: no issues found in **272** source files |
| `pytest -m "not live and not integration and not manual"` | 0 | **3016 passed / 0 failed / 0 skipped / 1 deselected** (prior 4 failures resolved) |
| `construction-agent validate --json` | 0 | `ok=true`; `schema_version=37` |
| `construction-agent data-quality table-inventory --json` | 0 | `schema_version=37`; **0 unmapped live tables** |
| `construction-agent data-quality no-writeback-proof --json` | 0 | `proof_passed=true`; `no_raw_values_persisted=true` |
| `second-brain data-quality phase-08a-gates --json` | 0 | `ok=true`; 8 pass / 1 warn / 0 fail / 3 deferred; not overstated |
| `second-brain data-quality phase-08b-gates --json` | 0 | `ok=true`; 16 pass; not overstated |
| `second-brain data-quality phase-08c-gates --json` † | 0 | `ok=true` / `proof_passed=true`; 21 pass / 1 warn; not overstated |
| `second-brain data-quality phase-08d-gates --json` † | 0 | `ok=true`; 14 pass / 0 fail; `ready_to_serve=true`; not overstated |
| `second-brain mcp status --json` | 0 | `ready_to_serve=true`; `serve_blockers=[]`; `mcp_sdk_available=true` |
| `second-brain mcp no-raw-access --json` † | 0 | `proof_passed=true` (7 surfaces) |
| `second-brain mcp no-writeback --json` † | 0 | `proof_passed=true` (7 surfaces) |

† **Command-spelling resolution** (prompt vs. live CLI, per `cli/second_brain.py`): `financial
data-quality phase-08c-gates` → `data-quality phase-08c-gates`; `mcp data-quality phase-08d-gates` →
`data-quality phase-08d-gates`; `mcp data-quality no-raw-access-proof` → `mcp no-raw-access`; `mcp
data-quality no-writeback-proof` → `mcp no-writeback`.

**Note on evidence re-stamps.** As in Prompt 00, the gate/proof builders rewrite their own evidence
files (`generated_utc` / `repo_sha`) as a side effect; those incidental re-stamps across other phases
were **reverted** so this commit stays surgical. The authoritative run outputs are under
`validation-outputs-prompt-01/`.

---

## 6. Stop-condition check (all clear)

| Stop condition | Found? |
|---|---|
| Raw-content persistence | No — `no_raw_values_persisted=true`; both MCP proofs `proof_passed=true` |
| External writeback | No — no-writeback proofs pass; the only code change is tests |
| Missing no-raw / no-writeback proof | No — all present and passing |
| Unresolved high-impact review items entering an approved source manifest | N/A — no approved source manifest exists yet |
| Unapproved Obsidian notes indexed | N/A — no Obsidian loader/indexing introduced |
| Semantic retrieval bypassing Research Packet / Evaluation | N/A — no semantic retrieval exists yet |

No stop condition triggered. The 0-receipt operator DB and the (now-resolved) SDK-presence test gap are
not safety regressions — the no-raw/no-writeback proofs pass and `ready_to_serve=true` is the documented
SDK-present state.

---

## 7. Verdict

Phase 08D's closeout **holds against current repo truth**: MCP runtime operational
(`ready_to_serve=true`, SDK present), the receipt substrate and operational serve proof are verified,
gates report 14 pass with readiness not overstated, the no-raw and no-writeback proofs pass, the config
preview is preview-only and safe, and the evidence bundle is complete and consistent.

**Resolved:** the SDK-presence test inconsistency — the four Prompt-13/14 tests are now SDK-state-aware
and the suite is **fully green (3016 passed)**. **Carried forward:** **G-02** (operator-DB MCP runtime
receipt population = 0) to `Prompt_04_MCP_Runtime_Receipt_And_Denial_Smoke_Preflight`; the 08C
forecast-readiness warning (external Procore dependency) preserved. No stop condition triggered.
**Proceed to Phase 09 Prompt 02** (attached-audit-package gap preflight remediation).
