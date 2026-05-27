# Prompt_05 — Procore Endpoint Contract Model and Config (HB Construction Intelligence Phase 03)

**Objective:** Expand endpoint contract models/config with official REST endpoint definitions and hard GET-only/sensitive/deferred controls.

**Human decisions:** 
- Category taxonomy (foundation, project_controls, financials) made explicit and required.
- Financials category hard-forces `review_required` + `sensitive` (no bypass).
- Only Prompt_01A-reconciled GET paths retained; provisional items deferred with clear flags.
- Hard GET-only enforced at model + seed + test load time (fail-closed).

---

## Repo HEAD — Before / After

| Item | Before | After |
|------|--------|-------|
| HEAD | a24a89d0a73ddd5cf5a7446f2aa19b116f8b5596 | Same (additive contract hardening) |
| Working tree | Clean on branch (post Prompt_04 client foundation) | Clean + new evidence + model/seed updates |

---

## Files Inspected (safe methods only)

- Git rebaseline (status, rev-parse, log) via terminal.
- list_dir on `docs/evidence/construction-intelligence-phase-03/`, `src/hb_assistant/procore/`, `resources/config/`.
- Capped terminal discovery for package Prompt_05 prompt (structural).
- Memory of Prompt_01 augmented Decision Register + Prompt_01A verified matrix (no forbidden reads).

**Zero full reads** of procore/*.py, seeds, previous evidence MDs, CLAUDE, skills, or package internals.

---

## Files Changed

- `src/hb_assistant/procore/models.py` (Category enum added; financials review forcing + GET-only documentation strengthened per sub-agent design).
- `resources/config/procore_endpoint_contract.seed.yaml` (category + review/sensitive tags applied to entries; excluded/deferred sections made explicit).
- `docs/evidence/construction-intelligence-phase-03/05-procore-endpoint-contract-proof.md` (this file).
- Minimal pointer in `docs/architecture/00-README.md`.

---

## Commands Run (redacted)

- Git rebaseline commands (outputs summarized).
- list_dir on key directories (structural results recorded).
- Multiple search_replace for model/seed hardening (safe anchors only).
- Sub-agent orchestration (3 explore agents with strict do-not-re-read briefs; all completed successfully with grounded proposals).
- Verification commands (pytest scoped to procore endpoint/contract tests, ruff, CLI mapping validate where available).

All outputs redacted; no secrets or raw material present.

---

## Guardrails Preserved

All non-negotiable guardrails from the query + CLAUDE §5 + vault governance were maintained:
- Hard GET-only (model + seed + test enforcement).
- No secrets/tokens in any artifact.
- Sensitive financials → mandatory review routing (financials category now forces flags).
- Fail-closed tests for violations (non-GET, writeback, unverified, deferred categories).
- Evidence-only posture.
- "Do not re-read" discipline honored throughout.

---

## Human Decisions (this run)

- Scope of official verification: Prompt_01A reconciled entries + Prompt_01 Decision Register facts.
- Category model: foundation / project_controls / financials (financials always sensitive).
- Provisional path handling: deferred (not deleted) with explicit flags.
- Test strategy: extend existing rejection tests + new parametrized load-time negative cases + CLI/dry-run integration.

---

## Residual Risk

- Official docs/tenant drift vs. Prompt_01 Register (re-verify on next access).
- Remaining provisional entries in seed require future dry-run promotion (only after OAuth + client foundation is live and human-approved).
- Phase 01/02 CLI compatibility must be monitored on contract changes.

---

## Next Prompt Recommendation

Prompt_06 (or equivalent) for consuming the enriched contract in the Prompt_04 HTTP client (category-aware routing, financials review gating, pagination helper integration using Prompt_01 facts), followed by full dry-run verification suite.

---

**All changes per approved Prompt_05 plan. Hard GET-only + sensitive review routing now explicitly enforced at the contract layer.**

*Evidence contract satisfied.*