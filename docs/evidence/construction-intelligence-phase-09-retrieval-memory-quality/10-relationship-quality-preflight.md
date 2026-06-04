# Phase 09 — Prompt 10: Cross-Source Relationship Quality Preflight

**Evidence artifact:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/10-relationship-quality-preflight.md`
**Machine-readable companion:** `10-relationship-quality-preflight.json` (+ `relationship-quality-mart.json`)
**Captured outputs:** `validation-outputs-prompt-10/`
**Gap:** G-08 (relationship substrate populated — 1,880 candidates / 1,671 promoted — but no quality mart)
**Audit date:** 2026-06-04 · **HEAD (audited):** `23e6d87` (worked at `e6d7579`) · **Schema:** V37 · **Version:** 1.3.0
**Posture:** Deterministic **read-only advisory** relationship-quality mart (**no new schema**) over the V25 cross-source relationship tables, plus a read-only CLI command. Emits **link ratios + confidence distribution + orphan/duplicate counts** only — never promotes, rejects, writes, or makes a determination. Reads the operator DB read-only (verified unmutated). **No LlamaIndex/embeddings/vector/semantic-retrieval code.**

---

## 1. Scope & guardrail posture

G-08 remediation, "relationship quality marts for link ratios, confidence, orphan/duplicate counts,
before semantic retrieval over the relationship graph." The guardrails forbid **automatic promotion**
and **final determinations**, so orphan / duplicate / confidence outputs are delivered as **quality
signals + source-coverage warnings** — never assignments or promotions. The mart is a derived read
model (no schema), computed read-only over the three V25 relationship tables; only counts / ratios /
enums are emitted (no raw content, source refs are hashes already). Nothing is promoted, rejected, or
written.

---

## 2. Live quality profile (read-only, operator DB)

| Signal | Live value |
|---|---|
| Candidates / promoted relationships / evidence trails | **1,880 / 1,671 / 1,880** |
| Promotion rate (relationships / candidates) | **0.889** |
| Confidence (candidates) | deterministic **1,671** · strong_heuristic **51** · weak_heuristic **158** · (model/human/rejected/stale 0) |
| Link ratios (candidates) | promoted **0.889** · review-required share · deterministic share · model_proposed **0** |
| **Orphan total** (reachability-honest) | **0** — every relationship reaches an evidence trail via its candidate |
| `relationship_direct_evidence_trail_absent` (informational) | **1,671** — the 07D promotion path didn't copy `evidence_trail_id` forward; **still traceable via candidate**, so *not* an orphan |
| **Multi-edge pairs** (near-duplicate) | **46** — one source→target pair under >1 `relationship_type` (exact dups blocked by the UNIQUE edge constraint) |
| Stale / unresolved | 0 |

**Key finding:** a naive "relationship lacks an evidence trail" check would flag **all 1,671** promoted
relationships, but every one is fully traceable to a trail via `candidate_id → candidate.evidence_trail_id`
(promoted_missing_candidate = 0, candidate_missing_evidence_trail = 0). The mart therefore counts a true
evidence-orphan only when a relationship reaches a trail by **neither** path (**0** live), and surfaces
the missing *direct* link as an **informational denormalization** signal (1,671) — not a warning. The
only advisory warning is **46 multi-edge pairs**.

---

## 3. Advisory-only / no-determination attestation

`build_relationship_quality_proof` → `proof_passed=true`, `advisory_only=true`,
`no_determination_attested=true`, `guard_violation=false`, `raw_content_findings=[]`. The **8 guard
`CHECK(=0)` columns** on each of the three relationship tables (`raw_*_persisted`, `signed_url_persisted`,
`download_url_persisted`, `external_writeback_performed`, …) re-attested clean (sum 0). The mart **writes
nothing** — operator relationship-table counts are **unmutated** (before == after: 1,880 / 1,671 / 1,880).

---

## 4. Reusable helper + CLI + tests (committed code)

`src/hb_assistant/construction/second_brain/relationship_quality_mart.py` —
`build_relationship_quality_mart` + `build_relationship_quality_proof` (read-only `?mode=ro`; counts /
ratios / enums only; reuses `_risk_category` + `HIGH_IMPACT_CATEGORIES`). Fully typed; `ruff` + `mypy
src` clean (**279** files).

`src/hb_assistant/cli/second_brain.py` — a new read-only command
`hb-assistant second-brain data-quality relationship-quality --json [--project]` (mirrors `review-load`
+ `_emit_08c`; exit 0/3).

`tests/test_phase_09_relationship_quality_mart.py` (5 tests): normal link-ratios + guard-clean; empty
substrate fail-soft; stale-schema graceful; no-raw injection fail-closed (value never echoed, DB row
count unchanged → no-writeback); orphan + duplicate signals (advisory, do not fail the proof).

---

## 5. Validation commands & results (HEAD `e6d7579`, `.venv/bin/python3.12`)

Captured under `validation-outputs-prompt-10/`.

| Command | Exit | Result |
|---|---|---|
| `python -m compileall -q src tests` | 0 | ok |
| `ruff check .` | 0 | All checks passed! |
| `mypy src` | 0 | no issues / **279** files |
| `pytest -m "not live and not integration and not manual"` | 0 | green (prior 3046 + 5 new = **3051 passed**) |
| `construction-agent validate --json` | 0 | `ok=true` (4/4); `schema_version=37` |
| `construction-agent data-quality table-inventory --json` | 0 | schema 37; **0 unmapped live tables** |
| `construction-agent data-quality no-writeback-proof --json` | 0 | `proof_passed=true` |
| `second-brain data-quality phase-08a / phase-08b-gates --json` | 0 | `ok=true` |
| `second-brain mcp no-raw-access / no-writeback --json` | 0 | `proof_passed=true` |
| **`second-brain data-quality relationship-quality --json`** (new) | 0 | `proof_passed=true`; 1,880 candidates / 1,671 relationships; orphan_total 0; 46 multi-edge |

**`phase-08c-gates` deliberately skipped:** per the Prompt-02/05 disclosure it appends ~1,299 rows to
the append-only financial review ledger per call (a write to the operator DB), unrelated to the
relationship surface; skipping preserves this prompt's pristine-operator-DB posture. Evidence re-stamps
from the proof builders were reverted to keep the commit surgical.

---

## 6. Stop-condition check (all clear)

| Stop condition | Found? |
|---|---|
| Raw-content persistence | No — counts/ratios/enums only; forbidden-shape scan over the JSON columns clean; no raw bodies/URLs |
| Writeback | No — read-only `?mode=ro`; operator relationship-table counts unchanged (before == after) |
| Missing no-raw / no-writeback proof | No — relationship-quality proof + MCP no-raw/no-writeback proofs pass |
| Unresolved high-impact review items entering an approved source manifest | N/A — the mart promotes nothing; **no automatic promotion** |
| Unapproved Obsidian indexing / semantic retrieval bypass | N/A — no retrieval/embeddings/vector code added (preflight) |
| **Final relationship determination** | **No — orphan/duplicate/confidence outputs are advisory quality signals + warnings; no promotion, no rejection, no writes** |

No stop condition triggered.

---

## 7. Verdict

G-08 **remediated (advisory)**: the cross-source relationship graph is profiled — promotion rate
**0.889**, confidence distribution (deterministic 1,671 / strong 51 / weak 158), **0 true orphans**
(with the 1,671 missing *direct* evidence links surfaced as informational denormalization, not a
warning), and **46 multi-edge near-duplicate pairs** — with a verified **no-determination /
no-promotion / no-writeback** posture, the operator DB left unmutated. A reusable read-only mart helper,
a read-only CLI command, and 5 tests are committed (suite green). No stop condition triggered.
**Proceed to the remaining Phase 09 preflight prompts** (G-05 memory, G-10 corpus balance).
