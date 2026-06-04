# Phase 09 — Prompt 00: Repo Truth Audit & Phase 09 Rebaseline

**Evidence artifact:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/00-repo-truth-audit-and-rebaseline.md`
**Machine-readable companion:** `00-repo-truth-audit-and-rebaseline.json`
**Package manifest:** `HB_Construction_Intelligence_Phase_09_Retrieval_Memory_Quality_Implementation_Package/00_PACKAGE_MANIFEST.md` (planning label `v1.4.0-phase-09-planning`; package version `1.3.0`)
**Audit date:** 2026-06-04
**Posture:** Read-only audit + rebaseline. **No runtime code, tests, schema, or `pyproject` changed in this prompt.** The only files added are this evidence bundle, a README ledger entry, and one architecture record (`docs/architecture/120-…`). **No LlamaIndex / embeddings / vector store / semantic-retrieval code is introduced** (the explicit Prompt 00 preflight boundary).

---

## 1. Scope & guardrail posture

This prompt re-establishes a verified repo-truth baseline (current `main`, schema, package version,
README ledger, in-repo evidence, dirty state) before any Phase 09 retrieval/memory work, and **resolves
the one gap it owns** — **G-09** (report the repo baseline as safe literal values, not hashes/line
counts). The eight blocking gaps (G-01…G-08, G-10) are carried forward to preflight Prompts 01–11; Phase
09 build work begins only after those gates pass.

Repository truth (code, tests, runtime behavior, in-repo evidence) is authoritative over any planning
note. The local-first, read-only, no-writeback, no-raw, advisory-only posture is preserved unchanged.
Nothing here persists raw content, performs writeback, exposes raw stores / arbitrary SQL / a raw vector
index, or makes any final determination.

---

## 2. Audit matrix (repo truth vs. package assumption)

| Dimension | Package assumption | Repo truth (verified) | Source | Verdict |
|---|---|---|---|---|
| Audited HEAD | `23e6d870b8033fcea8bf4bacc167f8d2f6c29790` | `git rev-parse HEAD` = same | runtime-stamped `repo_sha` in proofs | ✓ exact match |
| Phase 08D target | `a24f2a75f5b019d495b891d433edb264c9426d2e` | ancestor of HEAD; `main` ahead **2** / behind **0** | `git rev-list --count`, `git merge-base --is-ancestor` | ⚠ diverged (§3) |
| Schema (current) | V37 | `LATEST_SCHEMA_VERSION = 37`; `validate` → `schema_version=37` | `store/migrator.py:17` | ✓ |
| Schema (Phase 09 proposed) | additive (later prompts) | **not present** (reserved for Prompt 12+) | n/a | ✓ correctly absent |
| Runtime package version | `1.3.0` (label `v1.4.0-phase-09-planning`) | `pyproject.toml:7` = `1.3.0` | `pyproject.toml` | ✓ (label-vs-runtime, §3) |
| README ledger | 08A Active · 08B/08C/08D Closed · 09 not started | exactly this | `README.md:25–31` | ✓ |
| Retrieval/memory build | absent (deferred to 09) | `second_brain/retrieval/` + `memory/` dirs exist; **no LlamaIndex/embeddings/vector index** | §6 | ✓ correctly absent |
| Dirty state | — | untracked `.claude/`, `.code-graph/` only; no tracked changes | `git status --porcelain` | ✓ |

---

## 3. Divergence & version notes

**Divergence (drives the validation choice).** `main` is two commits ahead of the Phase 08D target:

- `23e6d87` — Phase 08D Prompt 15 operational MCP-bridge closeout + final validation.
- `7189daf` — Procore live-sync hardening (endpoint-specific per-page limits + commitment-compliance
  parent filtering) — a **runtime** change.

Because HEAD is not the commit at which the full matrix was last recorded green (the 08D closeout was at
`23e6d87` itself, but the Procore runtime change `7189daf` precedes it on the branch), the **full
validation suite is re-run fresh** at HEAD `23e6d87` rather than cited — see §7.

**Version label vs. runtime version.** The package/commit-subject convention uses
`v1.4.0-phase-09-planning`; the runtime version is **`1.3.0`** (`pyproject.toml:7`). This is the
established repo pattern (every Phase 08C/08D commit carried `v1.4.0-phase-0Nd-planning` while `pyproject`
stayed `1.3.0`) — a planning-package label, not a runtime version. **No version bump in this prompt.**

---

## 4. Phase 08A–08D closeout audit

| Phase | Ledger state (`README.md`) | This-run verdict |
|---|---|---|
| 08A — Second-Brain Runtime | Active (Prompts 02–15; 09 deferred) | `phase-08a-gates` `ok=true`, 8 pass / 1 warning / 0 fail / 3 deferred, `readiness_overstated=false` |
| 08B — Automation Delivery & Observability | Closed | `phase-08b-gates` `ok=true`, 16 pass / 0 warning / 0 fail / 0 deferred, `readiness_overstated=false` |
| 08C — Financial Readiness | Closed (Prompts 00–14) | `phase-08c-gates` `ok=true` / `proof_passed=true`, 21 pass / 1 warning / 0 fail, `readiness_overstated=false` |
| 08D — Local MCP Bridge | Closed, operational (Prompts 00–15) | `phase-08d-gates` `ok=true`, 14 pass / 0 deferred, `ready_to_serve=true`, `serve_blockers=[]`, `readiness_overstated=false`; `mcp no-raw-access` + `mcp no-writeback` `proof_passed=true` |

The construction-side legacy proof (`construction-agent data-quality no-writeback-proof`) is
`proof_passed=true` / `no_raw_values_persisted=true` at schema V37, covering Phases 07A/07B/07C/07D.

---

## 5. Architecture / runbooks / contracts audit

- **Architecture records:** Phase 08D occupies `docs/architecture/106`–`119`. This prompt adds
  `docs/architecture/120-phase-09-retrieval-memory-quality-repo-truth-rebaseline.md` (preflight posture +
  gap register). No earlier record assumes a vector/semantic layer.
- **Runbooks** (`docs/runbooks/`): email (06), SharePoint/OneDrive (06a), Procore (06b), second-brain
  daily-brief scheduling (08a), Claude Desktop MCP configuration (08d). No Phase 09 retrieval runbook yet
  (added by a later preflight/build prompt).
- **Standing MCP boundary:** `phase_08a_agent_tool_contract.json` ·
  `"mcp_future_exposure_rule": "Expose workflows only; never expose stores."` The Phase 09 MCP retrieval
  wrapper must remain a workflow wrapper — never raw vector search, never raw store access.
- **Guardrail enforcement intact (unchanged this prompt):** mailbox read-only at four layers; no-raw
  output fence + V24–V37 guard `CHECK(… = 0)` columns; static no-writeback mutation scans. Re-attested by
  the passing no-writeback / no-raw proofs in §4/§7.

---

## 6. Retrieval / memory absence audit

`second_brain/retrieval/` (the Phase 08A allowlisted **Retrieval Broker A03**) and `second_brain/memory/`
(the Phase 08A **Memory Curator A07** review substrate) exist, but **no semantic-retrieval
implementation does**:

- `python -c "importlib.util.find_spec('llama_index')"` → **not installed**.
- No `faiss` / `chromadb` / `sentence_transformers` in `src/` (the `grep` matches were the word
  "embeddings" in comments/contracts only — no vector library import).
- Retrieval today is deterministic and allowlisted via the broker; memory candidates are source-linked
  and review-controlled.

This is the correct precondition for Phase 09: the broker seam is declared, but no embeddings/vector code
exists, and semantic retrieval (when it lands) is gated behind Research Packet / Output Evaluation.

The structural footprint of the still-open data-quality gaps is corroborated by `table-inventory` at
schema V37: `operational_populated: 66`, `operational_empty_expected: 78`, **`operational_empty_blocking:
9`**, with **0 unmapped live tables** (`in_db_not_in_contract: []`; the 4 `in_contract_not_in_db` are the
`procore_sync_*` live-sync tables absent in the local DB — benign).

---

## 7. Validation commands & results

All commands run at HEAD `23e6d87` on 2026-06-04 with the real `.venv/bin/python3.12` toolchain.
Captured outputs: `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/validation-outputs/`.

| Command (as run) | Exit | Result |
|---|---|---|
| `python -m compileall -q src tests` | 0 | ok |
| `ruff check .` | 0 | All checks passed! |
| `mypy src` | 0 | Success: no issues found in **272** source files |
| `pytest -m "not live and not integration and not manual"` | 1 | **3012 passed / 4 failed / 0 skipped / 1 deselected** (4 pre-existing 08D SDK-presence failures — §8) |
| `construction-agent validate --json` | 0 | `ok=true`; `schema_version=37`; 4/4 checks |
| `construction-agent data-quality table-inventory --json` | 0 | `schema_version=37`; contract 171 / live 167; **0 unmapped live tables** |
| `construction-agent data-quality no-writeback-proof --json` | 0 | `proof_passed=true`; `no_raw_values_persisted=true` |
| `second-brain data-quality phase-08a-gates --json` | 0 | `ok=true`; 8 pass / 1 warn / 0 fail / 3 deferred; not overstated |
| `second-brain data-quality phase-08b-gates --json` | 0 | `ok=true`; 16 pass / 0 / 0 / 0; not overstated |
| `second-brain data-quality phase-08c-gates --json` † | 0 | `ok=true` / `proof_passed=true`; 21 pass / 1 warn / 0 fail; not overstated |
| `second-brain data-quality phase-08d-gates --json` † | 0 | `ok=true`; 14 pass / 0 deferred; `ready_to_serve=true`; not overstated |
| `second-brain mcp no-raw-access --json` † | 0 | `proof_passed=true` |
| `second-brain mcp no-writeback --json` † | 0 | `proof_passed=true` |

† **Command-spelling resolution** (the prompt's spellings vs. the live CLI, confirmed from
`cli/second_brain.py`): `second-brain financial data-quality phase-08c-gates` → `second-brain
data-quality phase-08c-gates`; `second-brain mcp data-quality phase-08d-gates` → `second-brain
data-quality phase-08d-gates`; `second-brain mcp data-quality no-raw-access-proof` → `second-brain mcp
no-raw-access`; `second-brain mcp data-quality no-writeback-proof` → `second-brain mcp no-writeback`. No
Phase 09 gate command exists yet (none is introduced by this audit-only prompt).

**Note on evidence re-stamps.** The gate/proof builders rewrite their own evidence files (refreshing
`generated_utc` / `repo_sha`) as a side effect of running. Running the suite above re-stamped 22 committed
evidence files across Phases 06/07A/08B/08C/08D with **timestamp/SHA churn only** (verdicts unchanged);
those incidental re-stamps were **reverted** so this rebaseline commit stays surgical. The authoritative
run outputs are preserved under `validation-outputs/`.

---

## 8. Known failures (pre-existing, out of Phase 09 scope)

Four tests fail at HEAD — all in Phase 08D, all asserting the **SDK-absent** posture:

```
tests/test_phase_08d_no_raw_access.py::test_startup_check_passes_and_drops_prompt_13_blocker
tests/test_phase_08d_no_raw_access.py::test_data_quality_gate_no_raw_access_now_passes
tests/test_phase_08d_no_writeback.py::test_startup_check_passes_and_drops_prompt_14_blocker
tests/test_phase_08d_no_writeback.py::test_data_quality_gate_no_writeback_now_passes
```

**Root cause.** These tests (last edited in Phase 08D **Prompt 14**, `033ec76`) hard-assert
`status["ready_to_serve"] is False` and `serve_blockers == ["mcp_sdk_not_installed"]` — the posture when
the optional `mcp` SDK is **absent**. Phase 08D **Prompt 15** (`23e6d87`, this HEAD) installed the
optional SDK (`mcp 1.27.2`) and made `ready_to_serve` truthful (`policy.py:188,215` — `find_spec("mcp")`
→ `ready_to_serve = foundation_ok and not serve_blockers`), but did **not** update those two
Prompt-13/14 test files. With the `[mcp]` extra installed in this venv, the assertions invert.

**Classification.** Pre-existing at HEAD; entirely within Phase 08D; **not introduced by Phase 09**
(no code changed). **Not a safety stop-condition** — the `mcp no-raw-access` and `mcp no-writeback`
proofs both report `proof_passed=true`, and `phase-08d-gates` reports 14 pass / 0 fail with
`readiness_overstated=false` and `ready_to_serve=true` (the documented **correct** state when the SDK is
present). Remediation (make the SDK-absent assertions SDK-state-aware) is an 08D test-hygiene follow-up,
**out of scope** for this audit-only Prompt 00.

---

## 9. Gap register carry-forward (G-09 resolved; rest classified)

From the package `33_PHASE_08D_GAP_REGISTER.md`. Prompt 00 **owns and resolves G-09**; the rest route to
their owning preflight prompt. Phase 09 build work (Prompt 12+) is blocked until the "Blocks 09 = Yes"
gaps are resolved or waived.

| Gap | Summary | Sev | Blocks 09? | Owning preflight prompt |
|---|---|---|---|---|
| G-01 | Generated-output tables present but 0 rows | high | Yes | Prompt 03 |
| G-02 | MCP runtime source-family population 0 | high | Yes | Prompt 04 |
| G-03 | Review queue ~66.5k items, `review_not_performed=true` | high | Yes | Prompt 05 |
| G-04 | Currency null; period nearly null; WBS/cost-code orphan risk | high | Yes | Prompt 06 |
| G-05 | Memory tables/workflows present but unpopulated | medium | Yes | Prompt 07 |
| G-06 | Automation/delivery receipts unpopulated | medium | Yes | Prompt 08 |
| G-07 | Vault notes lack SQLite-linked frontmatter (count 0) | medium | Yes | Prompt 09 |
| G-08 | No relationship-quality marts | medium | Yes | Prompt 10 |
| **G-09** | **Baseline reported as hashes/line counts, not safe literals** | medium | **No** | **Prompt 00 (resolved here)** |
| G-10 | Corpus Procore/financial-weighted; other families empty | medium | Yes | Prompt 11 |
| G-11 | Oversized evidence files need summarized companions | low | No | Prompt 02 |

**G-09 resolution.** The repo-truth baseline is emitted as **safe literal values** — branch (`main`),
HEAD SHA, Phase 08D target SHA, target-equality boolean, ahead/behind compare summary, and repo-relative
dirty paths — in this artifact and its `.json` companion (§2, and the JSON `repo_truth_safe_literals`
block), rather than opaque hashes or line counts.

---

## 10. Stop-condition check (all clear)

| Stop condition | Found? |
|---|---|
| Raw-content persistence | No — `no_raw_values_persisted=true`; both MCP proofs `proof_passed=true` |
| External writeback | No — no-writeback proofs pass; no mutation introduced |
| Missing no-raw / no-writeback proof | No — all present and passing |
| Unresolved high-impact review items entering an approved source manifest | N/A — no approved source manifest exists yet |
| Unapproved Obsidian notes indexed | N/A — no Obsidian loader / indexing introduced |
| Semantic retrieval bypassing Research Packet / Evaluation | N/A — no semantic retrieval exists yet |

No stop condition triggered. (The 4 known failures in §8 are not stop conditions — they concern
SDK-present serve-readiness, the opposite of a safety regression.)

---

## 11. Rebaseline verdict

Current `main` at `23e6d87` is a **valid, verified Phase 09 preflight baseline**: HEAD matches the
package's audited commit (2 ahead of the 08D target, behind 0), schema is **V37**, runtime version is
**1.3.0**, the README ledger is accurate, Phases 08A–08D gate/no-writeback/no-raw proofs all pass with
readiness not overstated, **no LlamaIndex/embeddings/vector/semantic-retrieval code exists**, and the
"expose workflows only; never expose stores" boundary is declared.

**G-09 resolved.** **G-01…G-08, G-10** carried forward to preflight Prompts 01–11 (eight Phase-09
blockers). **Deferred/warning posture preserved:** one non-blocking 08C forecast-readiness warning; the
four 08D SDK-presence test failures (§8, non-blocking 08D follow-up); and the Phase 09 package not yet
migrated from `~/Downloads/` into the vault Package Registry (a separate governance action). No stop
condition triggered. **Proceed to Phase 09 Prompt 01** (attached-audit-package gap verification).
