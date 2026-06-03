# Phase 08D — Prompt 00: 08C Audit and 08D Rebaseline

**Evidence artifact:** `docs/evidence/construction-intelligence-phase-08d-mcp-bridge/00-repo-truth-audit-and-rebaseline.md`
**Package manifest:** `HB_Construction_Intelligence_Phase_08D_Local_MCP_Bridge_Implementation_Package/00_PACKAGE_MANIFEST.md` · `v1.4.0-phase-08d-planning`
**Audit date:** 2026-06-03
**Posture:** Read-only audit. **No runtime behavior, code, tests, schema, README, or `pyproject` changed in this prompt.** This artifact is the only file added.

---

## 1. Scope & guardrail posture

This prompt audits current `main` against the Phase 08D package's stated assumptions
(target commit, package version, schema version, README ledger, Phase 08C
evidence/architecture/runbooks/contracts) and confirms **no MCP layer exists yet**.
It establishes the verified baseline that every later Phase 08D prompt builds on.

Repository truth (code, tests, runtime behavior, repo evidence) is authoritative over
any planning note. The local-first, read-only, no-writeback, no-raw, advisory-only
posture is preserved unchanged. Nothing in this prompt exposes raw SQLite, arbitrary
SQL, raw files, raw Obsidian notes, direct Graph/Procore, email send, calendar update,
source-system writeback, raw financial payloads, signed/download URLs, raw prompts, or
raw responses.

---

## 2. Audit matrix (repo truth vs. manifest assumption)

| Dimension | Manifest assumption | Repo truth (verified) | Source | Verdict |
|---|---|---|---|---|
| Target commit | `2052f931fb77c3a58557d622fd672db1962a7ba2` | HEAD = `2052f931fb77c3a58557d622fd672db1962a7ba2` | `git rev-parse HEAD` | ✓ exact match |
| Schema version (current) | V36 | `LATEST_SCHEMA_VERSION = 36`; `validate` → `schema_version=36` | `src/hb_assistant/store/migrator.py:17` | ✓ consistent |
| Schema version (08D proposed) | additive V37 (10 MCP tables) | V37 **not yet present** (reserved for Prompt 02) | n/a | ✓ correctly absent |
| Runtime package version | `1.4.0-phase-08d-planning` (planning label) | `1.3.0` | `pyproject.toml:7`, `src/hb_assistant/__init__.py:6` | ⚠ label-vs-runtime distinction (see §3) |
| README ledger | 08A Active · 08B Closed · 08C Closed · 08D deferred | exactly this (08A Active; 08B Closed; 08C Closed Prompts 00–14; 08D handoff) | `README.md:25,27,29` | ✓ match |
| MCP presence | must be absent (deferred to 08D) | 0 server/bridge modules; `mcp_implemented: False`; gate `mcp_exposure` deferred | see §6 | ✓ absent |
| Phase 08C closeout | Closed, proofs pass | Closed; live `proof_passed=true`; gates 21 pass / 1 warning / 0 fail_blocking | see §4–§5 | ✓ closed |

---

## 3. Version audit — label vs. runtime version

The Phase 08D manifest and the commit-subject convention use the string
`v1.4.0-phase-08d-planning`. The runtime package version is **`1.3.0`** in both
`pyproject.toml:7` (`version = "1.3.0"`) and `src/hb_assistant/__init__.py:6`
(`__version__ = "1.3.0"`), confirmed at runtime (`hb_assistant.__version__ → 1.3.0`).

This is the **established repo pattern, not a drift**: across the entire Phase 08C
arc, every commit subject carried `v1.4.0-phase-08c-planning` while `pyproject`
remained `1.3.0` (see recent commits `2052f93`, `01d7c19`, `7a2b6ce`). The
`vX.Y.Z-phase-NN-planning` string is a **planning-package label** used in
manifest titles and commit subjects; it is not the runtime distribution version.

**Decision:** Prompt 00 performs **no version bump** — consistent with the audit-only
posture and with the 08C precedent.

---

## 4. Phase 08C closeout audit

Phase 08C (Financial Readiness) is **Closed (Prompts 00–14)** per `README.md:29` and
the in-repo evidence bundle at
`docs/evidence/construction-intelligence-phase-08c-financial-readiness/`. Key
artifacts and what they attest:

| Evidence file | Attestation |
|---|---|
| `final-validation-closeout.md` | Phase 08C closed; compileall exit 0; ruff clean; `mypy src` clean (259 files); `pytest -m "not integration and not live and not manual"` **2895 passed / 0 failed**; all 7 CLI surfaces exit 0; readiness not overstated. |
| `no-writeback-no-raw-financial-output-proof.json` / `.md` | `proof_passed=true`; no external writeback; no Procore mutation; no raw financial payloads; no raw prompts/responses; no signed/download URLs; no payment/claim/entitlement decisions. |
| `financial-no-writeback-proof.json` / `.md` | Guard columns: 10 tables, 0 missing, 0 violating; money never binary float (canonical decimal TEXT + integer minor units, no REAL); evidence redaction clean (13 files, 0 findings). |
| `phase-08c-gates-proof.json` / `.md` | **21 pass / 1 warning / 0 fail_blocking / 0 deferred_not_blocking**; `readiness_overstated=false`. |
| `schema-and-contract-proof.md` | Schema **V35 → V36** additive; 10 financial tables + advisory-only / money-storage / no-raw guards; contracts load clean. |

The **V35/V36** characterization (ten V35 financial tables + the V36 review-item
confidence label; money as canonical decimal TEXT + integer minor units, never binary
float) is quoted verbatim from `README.md:29`.

---

## 5. Architecture, runbooks & contracts audit

**Architecture records (Phase 08C):** `docs/architecture/97`–`105`
(`97-phase-08c-…repo-truth-rebaseline` through `105-phase-08c-forecast-readiness-gates`)
plus the `docs/architecture/construction-intelligence-phase-08c-*` set
(data-quality-gates, final-validation-closeout, financial-cli-operator-status,
no-writeback-no-raw-proof, review-required-routing). No 08C architecture record
implements or assumes an MCP/bridge layer.

**Runbooks present** (`docs/runbooks/`): `phase-06-operational-email-workflows.md`,
`phase-06a-operational-sharepoint-onedrive-workflows.md`,
`phase-06b-operational-procore-workflows.md`,
`phase-08a-second-brain-daily-brief-scheduling.md`. No MCP runbook exists yet
(Prompt 09/14 of Phase 08D will add them under the 08D package).

**Standing MCP contract rule** (the non-negotiable Phase 08D boundary):
`src/hb_assistant/resources/json/phase_08a_agent_tool_contract.json:55` —
`"mcp_future_exposure_rule": "Expose workflows only; never expose stores."`
Readiness marker: `phase_08a_agent_registry_contract.json:32` `"mcp_future_ready": true`.

**Guardrail enforcement re-attested intact (unchanged this prompt):**
- Mailbox read-only, four layers: YAML policy (`email_intelligence_deferred_policy.yaml`,
  `mailbox_writeback_allowed: false`) → MSAL scope (`auth/scope_policy.py`, runtime
  requests only `Mail.Read`) → Python adapter (`construction/store/repositories.py`) →
  SQLite `CHECK(mailbox_writeback_allowed = 0)` (`store/migrator.py`).
- No-raw output fence + redaction: V35/V36 guard `CHECK(… = 0)` columns + static scan
  (`construction/data_quality/safety.py`) + content-leak regex
  (`construction/second_brain/financial_review_routing.py`).
- No external writeback: static mutation scan
  (`construction/second_brain/financial_no_writeback.py`).

---

## 6. MCP-absence audit

MCP is **completely absent** from the runtime and explicitly deferred to Phase 08D:

- **No server/bridge module:** `find src tests -iname '*mcp*'` → no results.
- **Marked not-implemented at 6 sites:** `cli/second_brain.py:172`,
  `construction/second_brain/reasoning.py:468`,
  `construction/second_brain/obsidian_index/indexer.py:295`,
  `construction/second_brain/agents/policy.py:152` and `:342`,
  `construction/second_brain/retrieval/broker.py:273` — all `"mcp_implemented": False`.
- **Deferred gate:** `phase_08a_data_quality_gates.json:14,25` lists `mcp_exposure`;
  `construction/second_brain/data_quality.py:236-238` maps it to
  `deferred_not_blocking` with `reason="mcp_not_implemented"`.
- **Future contract prepared (not implemented):** `mcp_future_exposure_rule`
  (`agent_tool_contract.json:55`) and `mcp_future_ready: true`
  (`agent_registry_contract.json:32`).

This is the correct precondition for Phase 08D: the workflow-only contract is
declared, but **no MCP code, transport, or store exposure exists**.

---

## 7. Validation commands & results

All commands run at HEAD `2052f93` on 2026-06-03 (read-only):

| Command | Result |
|---|---|
| `git rev-parse HEAD` | `2052f931fb77c3a58557d622fd672db1962a7ba2` (= manifest target) |
| `grep '^version' pyproject.toml` | `version = "1.3.0"` (line 7) |
| `python -c "import hb_assistant; print(hb_assistant.__version__)"` | `1.3.0` |
| `python -c "from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION; print(...)"` | `36` |
| `hb-assistant construction-agent validate --json` | 4/4 checks ok; `schema_version=36`; 6 projects / 14 sources |
| `hb-assistant second-brain data-quality phase-08c-no-writeback-proof --json` | `proof_passed=true`, `phase=08C`, `advisory_only=true` |
| `pytest tests/test_phase_08c_no_writeback_proof.py tests/test_phase_08c_financial_no_writeback.py -q` | **7 passed** |
| `find src tests -iname '*mcp*'` | no results (MCP absent) |

**Validation-subset rationale.** Per the prompt's validation-minimum rule, this
audit-only prompt runs the focused guardrail proofs for the touched surface (the
08C no-writeback/no-raw posture this rebaseline depends on) plus the schema/version
checks. The full matrix (`pytest … "not integration and not live and not manual"`
→ **2895 passed**) was recorded green at this exact HEAD in the Phase 08C
`final-validation-closeout.md`; no runtime change has occurred since, so it is not
re-run here. The full matrix will be re-run by Phase 08D Prompt 15.

---

## 8. Deferred / warning posture (to preserve)

- **Phase 08C forecast-readiness warning (carry-forward):** three not-yet-live-verified
  Procore endpoint shells (`purchase-order-detail-line-items`, `budget-details`,
  `budget-change-line-items`) keep `forecast_readiness` `source_coverage` at
  `deferred_not_blocking` — 1 non-blocking gate warning, an external dependency.
  Readiness is explicitly **not overstated** (`readiness_overstated=false`).
- **Deferred to Phase 09:** LlamaIndex/embeddings behind the retrieval broker; chat-session
  memory (substrate exists, no agent built). Phase 08D may wrap existing memory-review
  workflows only.
- **Out of Phase 08D scope:** remote MCP transport / network listener / desktop-fleet
  rollout; multi-user rollout. MVP transport is **stdio, local-only**.

---

## 9. Stop-condition check (all clear)

| Stop condition | Found? |
|---|---|
| 08C gates missing/failing/overstated while README marks 08C closed | No — gates 21 pass / 1 warning / 0 fail_blocking; `readiness_overstated=false` |
| 08C no-writeback / no-raw-financial-output proof missing/failing | No — live `proof_passed=true`; focused tests 7 passed |
| Existing MCP tool exposes SQL / raw store / direct Graph-Procore / writeback / final determination | N/A — no MCP layer exists |
| Guardrail (mailbox read-only, output fence, redaction) regressed | No — all four layers + fence + redaction intact, unchanged this prompt |

---

## 10. Rebaseline verdict

Current `main` at `2052f93` is a **valid, verified baseline for Phase 08D**:
target commit matches, schema is V36 (V37 correctly reserved), README ledger is
accurate, Phase 08C is genuinely closed with passing no-writeback/no-raw proofs, the
"expose workflows only; never expose stores" contract is declared, and **no MCP code
exists**. The only documented nuance is the planning-label-vs-runtime-version
distinction (§3), which is the existing repo convention and requires no change.

**Deferred/warning posture:** one non-blocking 08C forecast-readiness warning carried
forward (external Procore dependency). No stop-condition triggered. Proceed to Phase 08D
Prompt 01 (08C gap preflight).
