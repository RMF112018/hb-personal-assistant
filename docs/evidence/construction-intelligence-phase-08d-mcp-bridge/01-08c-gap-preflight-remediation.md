# Phase 08D — Prompt 01: 08C Gap Preflight Remediation

**Evidence artifact:** `docs/evidence/construction-intelligence-phase-08d-mcp-bridge/01-08c-gap-preflight-remediation.md`
**Package manifest:** `HB_Construction_Intelligence_Phase_08D_Local_MCP_Bridge_Implementation_Package/00_PACKAGE_MANIFEST.md` · `v1.4.0-phase-08d-planning`
**Run date:** 2026-06-03 · **HEAD:** `bcd622b` · **Schema:** V36 · **Runtime version:** 1.3.0
**Posture:** Read-only preflight (verification + classification). **No runtime behavior, code, tests, schema, README, or `pyproject` changed.** Closed Phase 08C evidence bundle kept immutable (see §5). This artifact is the only file added.

---

## 1. Scope & guardrail posture

This prompt resolves or explicitly classifies every verified Phase 08C gap and
re-runs the Phase 08C gates + no-writeback proofs to confirm the financial-readiness
baseline is still green before any MCP build. The local-first, read-only,
no-writeback, no-raw, advisory-only posture is preserved unchanged. Nothing here
exposes raw SQLite, arbitrary SQL, raw files, raw Obsidian notes, direct
Graph/Procore, email send, calendar update, source-system writeback, raw financial
payloads, signed/download URLs, raw prompts, or raw responses. No live Procore/Graph
call is performed — the 08C gate/proof code paths are deterministic read-only scans
and do not import `procore/live_gate.py`.

---

## 2. 08C gap register — disposition

The 08D package's `03_PHASE_08C_COMPLETION_AUDIT.md` enumerates exactly three 08C
gaps; all are non-blocking. Each is resolved or explicitly classified below.

| Gap | Description | Disposition | Evidence |
|---|---|---|---|
| **08C-G01** | Three Procore endpoint shells not live-verified (`purchase-order-detail-line-items`, `budget-details`, `budget-change-line-items`) → `forecast_readiness` warning. | **Preserved** as a deferred external dependency. Re-run confirms `fail_blocking=0` and `readiness_overstated=false`; the warning stays visible and is **not** converted into a readiness/forecast determination. No live evidence available to change it (live Procore out of scope). | §3 row [1]: `forecast_readiness=warning`, counts 21/1/0/0. |
| **08C-G02** | Forecasting remains out of Phase 08C scope despite the forecast-readiness gate. | **Classified** as a standing advisory constraint. The "readiness only; no forecast/determination" rule is carried into the MCP allowed-tools/prompt contracts in later 08D prompts (Prompt 08 prompts, Prompt 10 audit), not remediated here. | §3 attestations: `financial_determination_performed=false`, `payment_decision_performed=false`, `claim_or_entitlement_decision_performed=false`. |
| **08C-G03** | A stale nested command path `second-brain financial data-quality …` was historically referenced; the registered repo-truth path is `second-brain data-quality …`. | **Resolved (doc-alignment)**. The registered repo-truth paths below were exercised and exit cleanly; the stale path is not used and is not resurrected. No code change. | §3 — all commands run via the registered paths. |

**Registered repo-truth command paths (authoritative, used in §3):**
- `hb-assistant second-brain data-quality phase-08c-gates`
- `hb-assistant second-brain data-quality phase-08c-no-writeback-proof`
- `hb-assistant second-brain financial no-writeback-proof`
- `hb-assistant construction-agent data-quality no-writeback-proof`

No verified 08C gap requires remediation **code** — all three are
classify/preserve/doc-align.

---

## 3. Re-run results (read-only; HEAD `bcd622b`)

| # | Command | Result |
|---|---|---|
| 1 | `second-brain data-quality phase-08c-gates --json` | `ok=true`, `proof_passed=true`, `schema_version=36`, **status_counts = 21 pass / 1 warning / 0 fail_blocking / 0 deferred_not_blocking**, `readiness_overstated=false`, `required_fields_covered=true`, `missing_required_evidence=[]`. Sole non-pass gate: `forecast_readiness=warning` (08C-G01). |
| 2 | `second-brain data-quality phase-08c-no-writeback-proof --json` | `proof_passed=true`. Confirmations all true: `no_external_writeback`, `no_procore_mutation`, `no_raw_financial_source_payload`, `no_raw_prompts_or_responses`, `no_signed_or_download_urls`, `no_payment_or_claim_or_entitlement_decisions`. |
| 3 | `second-brain financial no-writeback-proof --json` | `proof_passed=true`. |
| 4 | `construction-agent data-quality no-writeback-proof --json` | `proof_passed=true`, `schema_version=36`, `no_live_call_performed=true`, `no_raw_values_persisted=true` (matrix-listed legacy proof; covers Phase 07A–07D surfaces — context confirmation, not 08C-specific). |

**Attestations (commands 1–3, all false — never overstated):**
`financial_determination_performed=false`, `payment_decision_performed=false`,
`claim_or_entitlement_decision_performed=false`, `external_writeback_performed=false`,
`raw_financial_payload_persisted=false`, `live_procore_call_performed=false`.

**Schema note:** the gates evaluator reports `schema_version=36` against
`schema_version_expected=35`; V36 is additive over the V35 baseline (the V36
review-item confidence label), so the contract still passes (`ok=true`). This is
expected and matches the Phase 08C closeout.

**Focused test subset (validation-minimum for touched surfaces):**
```
pytest tests/test_phase_08c_gates.py \
       tests/test_phase_08c_no_writeback_proof.py \
       tests/test_phase_08c_financial_no_writeback.py
→ 16 passed
```
Rationale: this preflight touches only the 08C gate/proof surfaces, so the focused
subset covers exactly the re-run code paths. The full matrix
(`pytest -m "not integration and not live and not manual"` → 2895 passed, recorded
at this baseline in the Phase 08C closeout) is deferred to Phase 08D Prompt 15 per
the validation-minimum rule.

---

## 4. Preserved warning / deferred posture

- **Forecast / source-coverage warning (08C-G01) is preserved as advisory/deferred.**
  `forecast_readiness=warning`; the three not-yet-live-verified Procore endpoint
  shells keep this a **deferred external dependency**, not a local data-quality
  defect and not a blocker (`fail_blocking=0`). It is **not** converted into a
  readiness, forecast, exposure, payment, claim, or entitlement determination
  (`readiness_overstated=false`; all financial-determination attestations false).
- No live-verified Procore evidence is available to change this disposition; live
  Procore is fail-closed behind `HB_PROCORE_LIVE=1` and out of Phase 08D scope.
- This warning must remain visible through Phase 08D; the MCP layer may surface
  readiness signals as advisory aids only and must never present them as
  determinations.

---

## 5. Closed-08C evidence immutability

The 08C gate/proof commands write proof JSON/MD into the **closed** Phase 08C
evidence bundle (`docs/evidence/construction-intelligence-phase-08c-financial-readiness/`),
overwriting only `generated_utc` + `repo_sha` on each run (substance — `proof_passed`,
counts, `schema_version` — is stable; verified the churn is sha/timestamp-only). Per
the governance rule that historical evidence is left immutable and annotated rather
than rewritten, this Prompt:
1. re-ran the proofs to confirm they still pass (results captured in §3), then
2. **restored** the 08C bundle to its committed state
   (`git checkout -- docs/evidence/construction-intelligence-phase-08c-financial-readiness/`),
   including the two files incidentally churned during Prompt 00.

The committed 08C proofs intentionally retain their generation-time sha; this
preflight does not rewrite them. The authoritative Prompt 01 result lives in this
08D artifact.

---

## 6. Stop-condition check (all clear)

| Stop condition | Found? |
|---|---|
| Any 08C gate returns `fail_blocking` | No — `fail_blocking=0` |
| Any no-writeback/no-raw proof `proof_passed=false` | No — all four `proof_passed=true` |
| `readiness_overstated=true` | No — `false` |
| Warning silently converted into a determination | No — preserved as advisory/deferred |
| Raw exposure / external writeback / live call introduced | No — read-only scans; all attestations false |

---

## 7. Verdict

No verified **blocking** Phase 08C gap exists. 08C-G01 is preserved as an advisory
deferred external dependency; 08C-G02 is classified as a standing advisory
constraint carried into the MCP contracts; 08C-G03 is resolved by using the
registered repo-truth command paths. All Phase 08C gates and no-writeback proofs
re-pass at HEAD `bcd622b` with `readiness_overstated=false`. The baseline is cleared
for **Phase 08D Prompt 02 (schema/contracts/table lifecycle)**.
