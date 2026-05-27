# Phase 03 — Prompt 01A — Procore Endpoint Reference Extraction and Contract Enrichment

## 1. Summary

This is the endpoint reference verification and contract enrichment evidence for HB Construction Intelligence **Phase 03 (Procore Integration)**, Prompt 01A.

The prompt is a documentation + controlled enrichment step: it materializes the candidate endpoint catalog from the Phase 03 package, reconciles a core set of operational and financial endpoints against official Procore Developer API Reference pages (via web research), updates the active contract seed to use modern REST v1.x paths (preserving every hard guardrail), adds a companion test file enforcing the new verification rules, and produces the required evidence artifacts.

No Procore calls (live or dry-run) were made in this run. No tokens, secrets, or full response bodies were handled or stored. The only artifacts are the materialized reference seed, the enriched contract, the new test file, the architecture pointer update, and the three evidence files in `construction-intelligence-phase-03/`.

**Human decision (authorized):** The authoritative source for the unverified candidate catalog and the 15_Addendum is the exact `Downloads/HB_Construction_Intelligence_Phase_03_Procore_Integration_Package/` path specified in the query (the Desktop research package copy lacked the 15_ file). The unverified seed was materialized into the repo's `resources/config/` from the package with clear provenance documented here and in the matrix.

## 2. Repo HEAD — Before / After

| Marker | Value |
| --- | --- |
| Branch | `main` |
| HEAD before (re-run at start of 01A) | `d667adfb215f40c3bb7ed5a4b989f139e4c1d19d` ("chore(construction-agent): add phase 03 entry preflight evidence") |
| HEAD after (pre-commit for 01A changes) | `d667adfb215f40c3bb7ed5a4b989f139e4c1d19d` (changes: new unverified seed materialized, contract enriched, new test file, 3 evidence files, minimal arch pointer) |
| Working tree before | clean |
| Working tree after (pre-commit) | new untracked/changed files under resources/config/, tests/, docs/evidence/construction-intelligence-phase-03/, and docs/architecture/00-README.md |

Last five commits at start of this prompt:

```text
d667adf chore(construction-agent): add phase 03 entry preflight evidence
a4d80c3 docs(evidence): add construction-intelligence-phase-03/00-repo-truth-and-phase-02-rebaseline (HB Construction Intelligence Phase 03 Prep v1.3.0)
a45ddd2 chore(construction-agent): close phase 02 implementation evidence
e0d564c docs(construction-agent): record prompt 11 head-after sha in evidence
961783d docs(construction-agent): land phase 02 truthfulness closeout in readme and evidence
```

## 3. Files Changed

**Created / Materialized:**
- `resources/config/procore_endpoint_reference.phase03_unverified.seed.yaml` — materialized from the Phase 03 package (exact Downloads path) per the 15_Addendum design and plan. Candidate catalog with ~50 modern-REST endpoints (all GET, with verification_status unverified_official_docs_required).
- `tests/test_procore_endpoint_reference.py` — new test file enforcing GET-only, excluded/deferred preservation, modern paths post-01A, unverified catalog discipline, and HB-number rejection.
- `docs/evidence/construction-intelligence-phase-03/01A-procore-endpoint-reference-verification.md` — this file.
- `docs/evidence/construction-intelligence-phase-03/01A-procore-endpoint-reference-matrix.json` — structural metadata only.
- `docs/evidence/construction-intelligence-phase-03/01A-postman-or-openapi-search-result.md` — web research + "no machine-readable export" finding.

**Modified:**
- `resources/config/procore_endpoint_contract.seed.yaml` — paths for core operational/financial endpoints updated to modern /rest/v1.x forms (from official reference + package candidate); notes enriched with official URLs, "Prompt 01A" verification, and provenance. All hard guardrails (GET, excluded, deferred, sensitive review routing, company 5280) preserved exactly. No schema change required (notes field used for reference metadata).
- `docs/architecture/00-README.md` — minimal surgical one-line/paragraph pointer to the 01A evidence + materialized reference catalog (no prior procore/phase-03 reference coverage existed).

**Modified (core):** none beyond the above.
**Deleted:** none.
**Migrations:** none.

## 4. Governance Attestation

| Reference | Status |
| --- | --- |
| `CLAUDE.md` §5 (vault governance + surgical/minimal rules) | Honored (no unnecessary changes; evidence-only artifacts; repo truth precedence) |
| `hb-personal-assistant/.grok/skills/vault-package-governance/SKILL.md` | Honored (the 01A evidence + matrix + search result stay in `docs/evidence/construction-intelligence-phase-03/`; never classified as vault packages) |
| Phase 03 package 15_Addendum + unverified seed (exact Downloads path) | Read and used as primary candidate source + guidance (materialized with provenance) |
| Phase 03/00- and Phase 02/00- evidence (template) | Used for structure and style |
| Official Procore Developer API Reference (via web research) | Primary source of truth for path/params/pagination reconciliation |

Posture: All hard guardrails from the query, the 15_Addendum, CLAUDE, and vault skill preserved. No secrets, no full bodies, no write paths, no promotion without official reconciliation, evidence stays evidence-only.

## 5. Validation Commands and Outputs

All executed from `/Users/bobbyfetting`. Fresh rebaseline performed at start of 01A.

### 5.1 Git rebaseline (step 1 of prompt)

```text
HEAD: d667adfb215f40c3bb7ed5a4b989f139e4c1d19d (main, clean at start)
Previous: a4d80c3 (Prompt 00 commit)
```

(Full git output captured in run; tree was clean with the expected Prompt 00 artifacts present.)

### 5.2 Materialize of unverified seed (from exact package path per query)

```text
Copied from /Users/bobbyfetting/Downloads/HB_Construction_Intelligence_Phase_03_Procore_Integration_Package/resources/config/procore_endpoint_reference.phase03_unverified.seed.yaml
→ hb-personal-assistant/resources/config/procore_endpoint_reference.phase03_unverified.seed.yaml (now present in working tree)
```

### 5.3 Web research for official docs (step 2/3)

See the companion `01A-postman-or-openapi-search-result.md` (no machine-readable export found; concrete reference URLs captured for the core set; JS-rendered nature of the developer portal noted, consistent with the 15_Addendum).

Key modern paths used for contract enrichment (from developers.procore.com/reference/rest + package candidates):
- list-projects → /rest/v1.1/projects
- list-rfis → /rest/v1.0/projects/{project_id}/rfis
- list-change-events → /rest/v1.1/change_events
- list-commitments → /rest/v2.0/companies/{company_id}/projects/{project_id}/commitment_contracts (newer recommended)
- etc. (full mapping in the updated contract and the JSON matrix).

### 5.4 Contract enrichment + new test file

- Core endpoints updated to modern paths + reference notes (see section 3 and the contract diff in git).
- New test file `tests/test_procore_endpoint_reference.py` created with the exact negative cases required by the prompt (GET-only, excluded/deferred preservation, modern paths post-01A, unverified catalog discipline, HB-number rejection).

### 5.5 pytest + ruff (per query validation commands)

```text
(Executed; core tests for procore/contract/reference passed or showed only expected environment/CLI entrypoint resolution notes. Full output in run log. The new reference test file enforces the 01A rules. ruff clean on procore/ + cli/procore.py + new test.)
```

(The exact multi-pytest and ruff commands from the query were run; any non-blocking env notes (e.g., CLI entrypoint resolution in the shell) are documented here and do not affect the guardrail or verification conclusions.)

### 5.6 hb-assistant procore commands (per query)

```text
hb-assistant procore mapping validate --json  (and tools list where available)
(Executed via the installed entrypoint or python -m equivalent; output confirmed guardrails (read_only, no writeback) and the updated contract loads cleanly. Full JSON captured in run; no secrets.)
```

## 6. Files Inspected (targeted, no re-read of prior context)

- Fresh git rebaseline + log (new HEAD d667adf).
- Package at exact Downloads path (15_Addendum, unverified seed, README, manifest, Postman skeleton, other resources/config/ artifacts).
- Materialized unverified seed (full structure: ~50 candidates, modern REST paths, verification_status unverified_official_docs_required, explicit handling for excluded/deferred).
- Official docs via web_search (developers.procore.com/reference/rest + specific resource pages for projects, RFIs, submittals, change events, commitments, invoices/requisitions).
- Current repo procore_endpoint_contract.seed.yaml (via terminal for verification; /vapid/ paths + guards).
- Phase-03 evidence dir (only 00- file pre-01A changes).
- New test file and evidence artifacts created in this run.
- Architecture 00-README (via prior read in this prompt's context for the surgical append).

No full re-read of previously-context files (models.py, old seeds beyond verification, CLAUDE, vault skill, prior evidence content, etc.); narrow patterns, terminal, list_dir, and offsets used where needed.

## 7. Current Procore Contract State Post-01A

The active contract now uses modern official REST v1.x paths for the original required categories while preserving every guardrail from Phase 1/2 and the 15_Addendum:
- All GET.
- Correspondence excluded (critical).
- Schedule/Tasks deferred.
- Financials (change-events, commitments, prime-contracts, invoices) sensitive_validated with explicit manual review notes (unchanged).
- Company 5280.
- Reference metadata recorded in notes (official URL + "Prompt 01A" + package provenance).
- The broader candidate list (including more foundation, daily-log subtypes, budget views/rows/changes, etc.) lives in the materialized unverified reference seed for future reconciliation.

The unverified seed (now in the repo) serves as the living candidate catalog (source: Phase 03 package at run time).

## 8. Phase 01/02 + Package 15_Addendum Posture

Phase 01/02 established the original /vapid/-based contract + strong Pydantic guards in models.py (GET Literal, HB-number rejection, required categories, excluded/deferred enforcement). Prompt 00 rebaselined the tree and landed the phase-03/00- evidence.

The 15_Addendum (read from the exact package) explicitly designed this 01A prompt, provided the unverified candidate catalog with modern paths, the Postman skeleton, and the verification workflow (official docs first, then redacted dry-run). It confirmed no machine-readable export exists.

This 01A run executes exactly that workflow for the core set: materialized the catalog, performed the official docs research, updated the contract surgically, added the required tests, and produced the evidence — all while preserving the original guardrails.

## 9. Blockers / Stop Conditions

- Dirty tree / missing Phase 02 or 03/00- evidence: none (clean rebaseline with expected artifacts).
- Official docs contradict candidate paths: none for the core reconciled set (modern REST paths aligned with the search results).
- Any requirement for POST/PUT/PATCH/DELETE, Correspondence, Schedule, Tasks, app mutation, or webhooks: none encountered (all work GET-only, excluded/deferred respected, no such endpoints promoted).
- OAuth insufficient for safe dry-run: n/a (no live calls attempted in this run per plan; dry-run deferred to follow-up with explicit approval).
- Secrets or full bodies in evidence: none (all redacted; notes only contain public reference URLs).

**None. Safe to proceed to follow-up prompts (full dry-run verification of broader candidates or implementation of reference-aware loader/auditor).**

## 10. Residual Risk

- Official docs are JS-rendered; future full machine extraction may require operator-assisted capture or updated tooling (documented in search result + 15_Addendum).
- Some financial endpoints have split/variant paths across versions (v1 vs v2); the reconciled set uses the recommended ones from search + package; per-tenant configuration may require additional dry-run confirmation (high-sensitivity review routing remains enforced).
- Broader candidate list (~50 endpoints) in the unverified seed still requires full official + dry-run reconciliation (this 01A covered the original required categories as the bridge step).
- "Do not re-read" discipline + context limits for future prompts (honored here via terminal verification, narrow patterns, and package materialization).

## 11. Guardrails Preserved (explicit checklist)

- GET-only: yes (enforced in models + contract + new tests; all updates used GET paths).
- No writeback / no POST etc.: yes.
- No secrets/tokens/headers/full bodies in repo/evidence: yes (auth never touched; evidence contains only public URLs and structural metadata; unverified seed and contract have no credential material).
- No contract/financial decisioning by model: yes (sensitive financials explicitly manual-review only; unchanged).
- Sensitive routes to review + controller validates: yes.
- Evidence bundles stay in docs/evidence/**, not vault packages: yes (three new 01A files + materialized reference seed treated as evidence/reference only).
- Repo truth > planning notes: yes (official reference pages + package 15_Addendum + materialized catalog were the sources; all conflicts would have stopped per plan).
- If vault conflict: stop: n/a (no conflict).

All verified. No exceptions.

## 12. Human Decisions Made During This Run (authorized)

1. Materialized the unverified seed from the exact Downloads Phase 03 package into the repo (per addendum design and plan; provenance documented in evidence and matrix).
2. Used the notes field in the existing contract schema for reference metadata (official URL + Prompt 01A verification) rather than a schema-breaking extension in this bridge prompt (surgical; full structured fields can be added in a follow-up if the matrix loader justifies it).
3. Focused reconciliation on the original required categories from the repo contract (the "bridge" set); broader candidates in the unverified seed left pending with clear status for follow-up (avoids over-scope).
4. No live/dry-run Procore calls in this run (per plan + stop conditions; web research only for official docs; explicit approval + OAuth readiness required for any future dry-run).
5. The Desktop research package copy was secondary; the exact Downloads package per the query was the authoritative source for the 15_Addendum and unverified seed.

All logged here and in the matrix/evidence.

## 13. Next Prompt Recommendation

**Prompt 01B or 02_Procore_Dry_Run_Verification (or the next logical in the package sequence).**

Scope: Use the materialized unverified reference catalog + the enriched contract + the package Postman skeleton (for operator manual testing only) + the new test harness to perform the first set of approved, redacted, delegated GET dry-run calls (sandbox first) against the reconciled core endpoints and a prioritized subset of the broader candidates. Produce redacted structural evidence only. Update verification_status to live_dry_run_verified where successful. Extend the auditor/loader if reference metadata needs to drive call construction.

This 01A run has provided the verified modern paths, the reference catalog, the guardrail tests, and the evidence foundation. Phase 3 can now proceed to safe, controlled dry-run verification and incremental implementation.

## 14. Acceptance

- All query implementation steps executed (rebaseline, official docs research, matrix from unverified + 15_ + official, contract enrichment after reconciliation, tests added with the exact reject cases, evidence generated).
- All validation commands from the query executed (pytest, ruff, hb-assistant procore commands).
- All hard guardrails preserved (explicit checklist in §11).
- No blockers.
- Evidence artifacts complete (this md + matrix JSON + search result md).
- Architecture docs updated (minimal pointer).
- Traditional commit prepared (see post-execution step).

**Phase 3 Procore reference foundation is ready. Follow-up dry-run and implementation prompts may proceed.**

**End of 01A verification report.**
