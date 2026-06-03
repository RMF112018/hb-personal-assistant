# 97 — Phase 08C Repo-Truth Audit and Rebaseline (Financial Readiness)

**Baseline**: Exact Phase 08B closeout `dcecea875ee8eb643cff8665c362eb0f1927df0a` (Prompt 10). Schema **V34**. Audit-only prompt (Prompt 00 for 08C); no code, no schema, no runtime change. Produces the 08C starting evidence bundle and updates architecture index.

**Objective** (per prompt): Verify live repo truth before Phase 08C implementation. Confirm HEAD, package/schema/README/evidence/arch, run 08B gate equivalents (automation_execution, no-writeback, automation/executor/brief status), re-audit financial substrate (Procore endpoint registry, financial tables, amount fields as Decimal-safe TEXT, source paths, cost-code/WBS, project-key joins, existing financial CLI, advisory labeling). Produce `00-repo-truth-audit-and-rebaseline.md` in `docs/evidence/construction-intelligence-phase-08c-financial-readiness/`. Stop if automation_execution not pass, 08B no-writeback fails, or README overstates. No repo code changes. Stage only required files. Include focused evidence. Do not close 08C.

**Evidence**:
- `docs/evidence/construction-intelligence-phase-08c-financial-readiness/00-repo-truth-audit-and-rebaseline.md` (primary; full matrix, ancestry, financial substrate re-audit with 32 endpoints / 15 tables / amount handling / CLI / proofs, guardrails, stop attestation).
- `docs/architecture/97-phase-08c-financial-readiness-repo-truth-rebaseline.md` (this).
- Update to `docs/architecture/00-README.md`.

## Design
- **Docs/evidence + arch index only.** No schema (stays V34), no CLI, no behavior. Re-uses 08B P00 rebaseline style + Phase 05 financial rebaseline style for the 00- deliverable.
- **Validation matrix (read-only, fresh).** Re-ran compile/ruff/mypy/pytest (safe), construction-agent validate, second-brain status/health, phase-08b-gates (16 pass incl. `automation_execution=pass`, `readiness_overstated=false`), no-writeback-proof (both second-brain + procore; repo_sha exact, financial tables explicitly guarded), procore validate (28/28), procore live financial summary (surface + guardrails + str amounts), package version (1.3.0). All green.
- **Financial substrate re-audit (direct, not assumed):** 32 endpoints in `endpoints.py` (owner 6 + commitments 6 + PO 3 + invoices 5 + RFQs/change 5 + budget 7); 4 in seed (sensitive_validated); 15 tables (V8 + V9 only; LATEST=34); amounts TEXT + source_field_path; Decimal only for compare/delta (str result, never stored, never float()); project_key + wbs/cost_code on all; existing `procore live financial` + exposure + obsidian register with exact advisory language ("advisory/review aid only — no entitlement/liability/contractual determinations; amounts are never summed"); proofs cover financial tables; SB integration minimal (policy only — expected pre-08C).
- **Stop check:** `automation_execution=pass` (fresh gate), both no-writeback `proof_passed=true`, README lists 08C only as explicit future handoff ("Handoffs are explicit — **08C** (financial readiness)"); no overstatement.
- **Arch + index:** New 97- (this) + surgical line in 00-README.md.
- **Commit:** Only the 00- evidence md + 97- + 00-README edit staged. Traditional manifest title in subject (v1.0.0 Prompt 00). Final agent output = only the commit summary block.

## Verification
- Ancestry: HEAD byte-for-byte target; ancestor OK; unrelated churn only (ignored).
- Matrix: see 00- md §2 (all green; 2834 safe pytest at identical HEAD; focused financial/08b subsets 100%).
- Gates/proofs: automation_execution=pass, 16/0, overstated=false; no-writeback proofs pass with exact sha + financial table guards enumerated.
- Financial: 32/15 confirmed, amount contract (str + Decimal-only), advisory labels, no raw, joins present (fresh CLI output shows str amounts + guardrails).
- Hygiene: new mds contain no secrets/raw (scanned via content + proof coverage); only 3 paths for commit.
- 08C not closed (this is Prompt 00 rebaseline).

**No stop conditions tripped. 08C substrate ready for implementation prompts.** See the 00- evidence for full detail + fresh command output.