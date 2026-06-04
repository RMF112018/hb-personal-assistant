# 120 — Phase 09 (Retrieval / Memory / Quality): Repo-Truth Rebaseline & Preflight Posture

**Status:** Preflight remediation (Prompt 00 — audit/rebaseline only).
**Schema:** V37 (unchanged — no migration in this prompt).
**Runtime package version:** `1.3.0` (unchanged).
**Audited HEAD:** `23e6d870b8033fcea8bf4bacc167f8d2f6c29790` (`main`).
**Phase 08D target commit:** `a24f2a75f5b019d495b891d433edb264c9426d2e` — `main` is **ahead by 2, behind by 0**.
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/00-repo-truth-audit-and-rebaseline.md` (+ `.json`).

---

## 1. Why this record exists

Phase 09 introduces semantic retrieval (LlamaIndex / embeddings / a vector index behind the existing
Retrieval Broker) and memory-quality / consolidation agents. That work is **gated**: it may only begin
after a sequence of preflight remediations (Prompts 01–11) closes the data-quality gaps left open at the
end of Phase 08D. This record captures the **verified baseline** Phase 09 builds on and the **gap
carry-forward** that constrains it. It deliberately adds **no retrieval code, no embeddings, no vector
store, and no schema migration** — consistent with the Prompt 00 preflight boundary.

Repository truth (code, tests, runtime behavior, in-repo evidence) is authoritative over any planning
note. The local-first, read-only, no-writeback, no-raw, advisory-only posture is preserved unchanged.

## 2. Verified baseline (repo truth vs. package assumption)

| Dimension | Package assumption | Repo truth (verified) | Source | Verdict |
|---|---|---|---|---|
| Audited HEAD | `23e6d87…` | `git rev-parse HEAD` = `23e6d87…` | runtime-stamped `repo_sha` in proofs | ✓ |
| Phase 08D target | `a24f2a7…` | ancestor of HEAD; `main` ahead 2 / behind 0 | `git rev-list --count` | ⚠ diverged (§3) |
| Schema | V37 | `LATEST_SCHEMA_VERSION = 37`; `validate` → `schema_version=37` | `store/migrator.py:17` | ✓ |
| Package version | 1.3.0 | `pyproject.toml:7` = `1.3.0` | `pyproject.toml` | ✓ |
| README ledger | 08A Active · 08B/08C/08D Closed · 09 not started | exactly this | `README.md:25–31` | ✓ |
| Retrieval/memory build | absent (deferred to 09) | `second_brain/retrieval/` + `memory/` dirs exist (08A substrate) — **no LlamaIndex/embeddings/vector index** | §5 | ✓ correctly absent |
| Dirty state | — | untracked `.claude/`, `.code-graph/` only; no tracked changes | `git status --porcelain` | ✓ |

## 3. Divergence note (drives the validation choice)

`main` is two commits ahead of the Phase 08D target:

- `23e6d87` — Phase 08D Prompt 15 operational MCP-bridge closeout + final validation.
- `7189daf` — Procore live-sync hardening (endpoint-specific per-page limits + commitment-compliance
  parent filtering) — a **runtime** change.

Because HEAD is **not** the last commit at which the full matrix was recorded green (that was the 08D
closeout), the audit-only shortcut used by the 08D Prompt 00 (cite the prior matrix instead of re-running)
does not apply here. The **full validation suite is re-run fresh** at HEAD `23e6d87` and captured in the
evidence bundle.

The `v1.4.0-phase-09-planning` string used in the commit subject / manifest title is a **planning-package
label**, not a runtime version bump — the same convention by which every Phase 08C/08D commit carried
`v1.4.0-phase-0Nd-planning` while `pyproject` stayed `1.3.0`. No version bump occurs in this prompt.

## 4. Standing guardrail boundary carried into Phase 09

- **Expose workflows only; never expose stores.** `phase_08a_agent_tool_contract.json` ·
  `mcp_future_exposure_rule`. The Phase 09 MCP retrieval wrapper (Prompt 22) must remain a workflow
  wrapper — never raw vector search, never raw store access.
- **Semantic retrieval is gated behind the Retrieval Broker, Research Packet, and Output Evaluation.**
  No agent may consume a vector index directly; insufficient context degrades or blocks, never overstates.
- **No raw vector index.** Embeddings/index source text is approved, source-linked generated output only —
  never raw email/document/calendar bodies, signed/download URLs, tokens, or secrets. The eight/twenty
  guard `CHECK(… = 0)` column families on the V24–V37 tables remain the substrate invariant.
- **Advisory only.** No final financial, legal, contractual, claim, entitlement, payment, schedule, or
  safety determination. Review tier, confidence class, source references, freshness metadata, and
  source-coverage warnings are preserved end to end.

## 5. Retrieval / memory absence audit

`second_brain/retrieval/` (the Phase 08A allowlisted Retrieval Broker A03) and `second_brain/memory/`
(the Phase 08A Memory Curator A07 review substrate) exist, but **no semantic-retrieval implementation
does**: no `llama-index` distribution is installed, no embedding model is wired, and no vector index is
built or persisted. Retrieval today is deterministic and allowlisted; memory candidates are source-linked
and review-controlled. This is the correct precondition for Phase 09 — the broker seam is declared, but
no embeddings/vector code exists.

## 6. Gap register carry-forward (G-01 … G-11)

From the package `33_PHASE_08D_GAP_REGISTER.md`. Prompt 00 **owns and resolves G-09**; the remaining gaps
are classified and routed to their owning preflight prompt. Phase 09 build work (Prompt 12+) is blocked
until the "Blocks Phase 09 = Yes" gaps are resolved or explicitly waived.

| Gap | Summary | Severity | Blocks 09? | Owning preflight prompt |
|---|---|---|---|---|
| G-01 | Generated-output tables present but 0 rows | high | Yes | Prompt 03 — Generated Output & Research Packet |
| G-02 | MCP runtime source-family population 0 (operational stdio proof now present) | high | Yes | Prompt 04 — MCP Runtime Receipt & Denial Smoke |
| G-03 | Review queue ~66.5k items, `review_not_performed=true` | high | Yes | Prompt 05 — Review Load & Human-in-Loop |
| G-04 | Currency null; period nearly null; WBS/cost-code orphan risk | high | Yes | Prompt 06 — Financial Data Completeness |
| G-05 | Memory tables/workflows present but unpopulated | medium | Yes | Prompt 07 — Memory Runtime & Review |
| G-06 | Automation/delivery receipts unpopulated | medium | Yes | Prompt 08 — Automation Delivery Receipt |
| G-07 | Vault notes lack SQLite-linked frontmatter (count 0) | medium | Yes | Prompt 09 — Obsidian Linkage |
| G-08 | No relationship-quality marts (linked/unlinked ratios, confidence, orphans) | medium | Yes | Prompt 10 — Relationship Quality |
| **G-09** | **Baseline reported as hashes/line counts, not safe literal values** | medium | **No** | **Prompt 00 — this record (resolved)** |
| G-10 | Corpus Procore/financial-weighted; other source families empty | medium | Yes | Prompt 11 — Corpus Balance & Source Coverage |
| G-11 | Oversized evidence files need summarized companions | low | No | Prompt 02 — Attached Audit Package Gap |

**G-09 resolution.** The repo-truth baseline is now emitted as **safe literal values** — branch (`main`),
HEAD SHA, Phase 08D target SHA, target-equality boolean, an ahead/behind compare summary, and
repo-relative dirty paths — in `00-repo-truth-audit-and-rebaseline.{md,json}`, rather than as opaque
hashes or line counts. The structural footprint of the still-open gaps is corroborated by
`table-inventory` (`operational_empty_blocking: 9`, `operational_empty_expected: 78`) at schema V37.

## 7. Stop conditions (all clear at this baseline)

No raw-content persistence, no writeback, no missing no-raw/no-writeback proof, no unresolved high-impact
review items entering an approved source manifest (no approved manifest exists yet), no unapproved
Obsidian indexing, and no semantic retrieval bypassing Research Packet / Evaluation (no semantic retrieval
exists yet). All eight no-writeback / no-raw / gate proofs re-ran green at HEAD `23e6d87` — see the
evidence bundle for the full command table.
