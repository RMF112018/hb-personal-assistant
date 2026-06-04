# Phase 09 — Prompt 11: Retrieval Corpus Balance & Source Coverage Preflight

**Evidence artifact:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/11-corpus-balance-preflight.md`
**Machine-readable companion:** `11-corpus-balance-preflight.json` (+ `corpus-balance-mart.json`)
**Captured outputs:** `validation-outputs-prompt-11/`
**Gap:** G-10 (corpus balance — classified `confirmed_imbalance` at Prompt 02; owning prompt = Prompt_11)
**Audit date:** 2026-06-04 · **HEAD (audited):** `23e6d87` (worked at `1feb8d1`) · **Schema:** V37 · **Version:** 1.3.0
**Posture:** Deterministic **read-only** corpus-balance **gate** + source-family **coverage proof** (**no new schema**) over the retrieval corpus, plus a read-only CLI command and a committed threshold policy seed. Emits per-family coverage + balance metrics + a fail-closed gate verdict only — never a determination. Reads the operator DB read-only (verified unmutated). **No LlamaIndex/embeddings/vector/semantic-retrieval code.**

---

## 1. Scope & guardrail posture

G-10 remediation, "corpus-balance gates and source-family coverage proof, before semantic retrieval."
The **retrieval corpus** = the families the Retrieval Broker may read (`ALLOWLISTED_SOURCE_FAMILIES`),
each backed by a local read-model table; the mart reuses the broker's allowlist, excluded-family set,
and reader registry (imported, not re-listed) so the corpus never includes a raw `EXCLUDED_FAMILIES`
family. Outputs are counts / shares / enums only; the gate verdict and coverage warnings are advisory
signals, never assignments or promotions.

---

## 2. Key finding — raw-ingestion vs retrieval-corpus balance

The G-10 claim ("procore/financial-heavy; brief/research/mcp/memory empty") was measured on the **raw
ingestion** tables. Measured at the **retrieval-corpus** level (what the broker actually reads,
post-read-model), the picture is more precise:

| Source family | Reader | Live row_count | Coverage |
|---|---|---|---|
| `phase_07d_source_evidence_trails` | yes | **1,880** | covered |
| `aging_exposure_report_items` | yes | **1,780** | covered |
| `cross_source_relationships` | yes | **1,671** | covered |
| `project_issue_history_items` | yes | **598** | covered |
| `project_risk_digest_items` | yes | **44** | covered |
| `approved_obsidian_generated_outputs` | yes | **0** | **empty** (`empty_family` warning) |
| `accepted_long_term_memory` | yes | **0** | **empty** (`empty_family` warning) |
| `meeting_prep_brief_sections` | no (deferred) | 0 | `deferred_no_reader` (`no_read_model` warning) |
| `review_controlled_correspondence_context` | no (deferred) | 0 | `deferred_no_reader` (`no_read_model` warning) |

**Total corpus rows 5,973 · covered families 5 / 7 reader-backed · dominant family
`phase_07d_source_evidence_trails` at share 0.31** (well under the 0.6 ceiling). So the *distribution*
across the populated families is reasonably balanced — the real gap is the **2 empty reader-backed
families** (`approved_obsidian_generated_outputs`, `accepted_long_term_memory`), which are owned by
sibling Phase 09 prompts (09 Obsidian linkage, 07 Memory).

---

## 3. Corpus-balance gate (fail-closed) + no-determination attestation

The committed policy seed (`resources/config/phase_09_corpus_balance_policy.seed.yaml`) requires **all
7 reader-backed families covered** (`min_covered_families=7`) and `max_dominant_family_share=0.6`. The
live gate therefore returns **`verdict=imbalanced`, `corpus_balance_ok=false`** with blocking reason
**`too_few_covered_families:5<7`** — the honest preflight readiness signal that the corpus is not yet
balanced because the obsidian + memory families are empty. The dominant-share check passes (0.31 ≤
0.6); coverage breadth is the blocker.

`build_corpus_balance_proof` → `proof_passed=true`, `policy_loaded=true`,
`no_determination_attested=true`, `guard_violation=false`, `raw_content_findings=[]`. The proof is
**independent of the balance verdict** — it validly *measures* an imbalanced corpus. Guard `CHECK(=0)`
columns on the corpus tables re-attested clean; the mart **writes nothing** (operator corpus-table
counts unmutated, before == after).

---

## 4. Reusable helper + CLI + seed + tests (committed code)

`src/hb_assistant/construction/second_brain/corpus_balance_mart.py` — `load_corpus_balance_policy`
(fail-closed) + `build_corpus_balance_mart` + `evaluate_corpus_balance_gate` +
`build_corpus_balance_proof` (read-only `?mode=ro`; counts / shares / enums; reuses the retrieval
allowlist + reader registry). Fully typed; `ruff` + `mypy src` clean (**280** files).

`resources/config/phase_09_corpus_balance_policy.seed.yaml` — threshold policy (7 / 0.6) + deferred
families (advisory; never a determination).

`src/hb_assistant/cli/second_brain.py` — read-only
`hb-assistant second-brain data-quality corpus-balance --json [--project]` (mirrors `review-load` +
`_emit_08c`; exit 0/3; surfaces `proof_passed`, `corpus_balance_ok`, `verdict`, per-family coverage,
dominant share, warnings).

`tests/test_phase_09_corpus_balance_mart.py` (5 tests): balanced corpus passes the gate; missing-policy
fail-closed; stale-schema graceful; no-raw injection fail-closed (value never echoed, DB row count
unchanged → no-writeback); imbalanced corpus measured-not-failed (gate `imbalanced`, `proof_passed=true`).

---

## 5. Validation commands & results (HEAD `1feb8d1`, `.venv/bin/python3.12`)

Captured under `validation-outputs-prompt-11/`.

| Command | Exit | Result |
|---|---|---|
| `python -m compileall -q src tests` | 0 | ok |
| `ruff check .` | 0 | All checks passed! |
| `mypy src` | 0 | no issues / **280** files |
| `pytest -m "not live and not integration and not manual"` | 0 | green (prior 3051 + 5 new = **3056 passed**) |
| `construction-agent validate --json` | 0 | `ok=true` (4/4); `schema_version=37` |
| `construction-agent data-quality table-inventory --json` | 0 | schema 37; **0 unmapped live tables** |
| `construction-agent data-quality no-writeback-proof --json` | 0 | `proof_passed=true` |
| `second-brain data-quality phase-08a / phase-08b-gates --json` | 0 | `ok=true` |
| `second-brain mcp no-raw-access / no-writeback --json` | 0 | `proof_passed=true` |
| **`second-brain data-quality corpus-balance --json`** (new) | 0 | `proof_passed=true`; `corpus_balance_ok=false`; `verdict=imbalanced`; 5/7 covered |

**`phase-08c-gates` deliberately skipped:** per the Prompt-02/05 disclosure it appends ~1,299 rows to
the append-only financial review ledger per call (a write to the operator DB), unrelated to the
corpus-balance surface; skipping preserves this prompt's pristine-operator-DB posture. Evidence
re-stamps from the proof builders were reverted to keep the commit surgical.

---

## 6. Stop-condition check (all clear)

| Stop condition | Found? |
|---|---|
| Raw-content persistence | No — counts/shares/enums only; forbidden-shape scan over corpus columns clean; no raw families counted |
| Writeback | No — read-only `?mode=ro`; operator corpus-table counts unchanged (before == after) |
| Missing no-raw / no-writeback proof | No — corpus-balance proof + MCP no-raw/no-writeback proofs pass |
| Unresolved high-impact review items entering an approved source manifest | N/A — the mart promotes/indexes nothing |
| Unapproved Obsidian indexing / semantic retrieval bypass | N/A — no retrieval/embeddings/vector code added (preflight); corpus read from the existing allowlist only |
| **Final determination** | **No — balance/coverage outputs are advisory signals + a fail-closed gate verdict; no determination** |

No stop condition triggered.

---

## 7. Verdict

G-10 **remediated (advisory)**: the retrieval corpus is profiled per source family (5/7 reader-backed
families covered — evidence-trails 1,880 / aging 1,780 / relationships 1,671 / issue 598 / risk 44 —
dominant share 0.31; obsidian + accepted-memory empty; 2 deferred no-reader families), and a
fail-closed corpus-balance gate returns the honest **`imbalanced`** verdict (`too_few_covered_families:5<7`)
with a verified **no-determination / no-writeback / guard-clean** posture, the operator DB left
unmutated. A reusable read-only mart + gate helper, a committed threshold policy seed, a read-only CLI
command, and 5 tests are committed (suite green). No stop condition triggered. **Proceed to the
remaining Phase 09 preflight prompt** (G-05 memory runtime & review — Prompt 07).
