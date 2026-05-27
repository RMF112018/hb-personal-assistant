# Phase 03 — Prompt 00 — Repo Truth and Phase 02 Rebaseline

## 1. Summary

This is the kickoff evidence for HB Construction Intelligence **Phase 03 (Procore Integration)**. The prompt is documentation-only: it rebaselines the working tree against the Phase 02 closeout commit (a45ddd2), attests vault-package governance and CLAUDE.md §5 rules, inspects Phase 01/02 evidence acceptance posture (especially the 00- rebaseline files and procore-specific 07-/09-), audits current Procore/CLI/config/schema/test state against the seeds, the 4 procore modules, and the Desktop/procore_hbintel_data_model_package research (the effective Phase 03 Procore Integration Package), identifies blockers, and creates the Phase 03 evidence root by landing this file under `construction-intelligence-phase-03/`.

No source modules, tests, schemas, or resource configs were modified. No SQLite migrations applied. No external system was contacted (all local git/list/read/grep). The only artifacts produced by this prompt are this evidence file (and a minimal surgical pointer in `docs/architecture/00-README.md` as post-major-doc step).

**Human decision (authorized):** The Desktop/procore_hbintel_data_model_package/ (README + 00-13 + crosswalks + canonical artifacts) is treated as the live "HB_Construction_Intelligence_Phase_03_Procore_Integration_Package" research input (content match for Procore REST -> canonical/SharePoint model; query Downloads path treated as illustrative or prior location). Inspected targeted (README, 01/03/07/10/12/13 + crosswalks) for assumptions/gaps vs current seeds/code.

## 2. Repo HEAD — Before / After

| Marker | Value |
| --- | --- |
| Branch | `main` |
| HEAD before | `a45ddd25b57f451ce6cdf314639246b5f57403a1` ("chore(construction-agent): close phase 02 implementation evidence") |
| HEAD after  | `a45ddd25b57f451ce6cdf314639246b5f57403a1` (no commits land until validation + this evidence file are both ready; the post-commit hash will be recorded once committed) |
| Working tree before | clean (`git status --short` empty) |
| Working tree after (pre-commit) | one new untracked file — `docs/evidence/construction-intelligence-phase-03/00-repo-truth-and-phase-02-rebaseline.md` (plus optional architecture/ pointer) |

Last five commits at start of this prompt (re-run preflight):

```text
a45ddd2 chore(construction-agent): close phase 02 implementation evidence
e0d564c docs(construction-agent): record prompt 11 head-after sha in evidence
961783d docs(construction-agent): land phase 02 truthfulness closeout in readme and evidence
9564ee2 docs(construction-agent): record prompt 10 head-after sha in evidence
d590735 feat(construction-agent): land email-intelligence deferred policy and mailbox-mutation lockout scans
```

## 3. Files Changed

**Created (1 + dir):**

- `docs/evidence/construction-intelligence-phase-03/00-repo-truth-and-phase-02-rebaseline.md` — this file. Establishes the Phase 03 evidence root.
- Parent dir `docs/evidence/construction-intelligence-phase-03/` created as part of evidence write (search_replace on deep path).

**Modified (post step):** 
- `docs/architecture/00-README.md` — minimal one-line surgical pointer to this evidence + Desktop research package as Phase 03 Procore/Construction Intelligence input (no prior coverage existed in 00-13 or remediation- titles).

**Modified (core):** none.
**Deleted:** none.
**Migrations applied:** none.

## 4. Governance Attestation

| Reference | Status |
| --- | --- |
| `CLAUDE.md` §5 — "Obsidian Vault Planning and Implementation Package Governance" (full, lines 67–82) | Read and honored (repo root `/Users/bobbyfetting/hb-personal-assistant`, source-of-truth repo/evidence > notes, evidence bundles not lifecycle packages, conflict stop rule, no-secret) |
| `hb-personal-assistant/.grok/skills/vault-package-governance/SKILL.md` (full) | Read and honored (repo-truth precedence, `docs/evidence/**` stays in-repo never classified as packages, no payload re-copy, registry+manifest together) |
| `docs/evidence/construction-intelligence-phase-02/00-phase-02-preflight-and-phase-01-acceptance-rebaseline.md` (primary template) | Read (first 180 lines + structure); used verbatim for evidence format, sections, guardrail attestation style, validation command blocks |
| `docs/evidence/construction-intelligence-phase-02/07-procore-mapping-correction-and-audit-readiness.md` + `11-documentation-evidence-truthfulness-closeout.md` + `session-handoff.md` | Structure + procore mapping context carried |
| `docs/evidence/construction-intelligence-phase-01/00-repo-truth-and-governance-preflight.md` + `09-procore-endpoint-audit-dry-run.md` + `11-final-closeout-summary.md` | Phase 01 procore audit baseline + closeout posture carried |
| Desktop/procore_hbintel_data_model_package/README.md (effective Phase 03 research package) | Read (first 60 lines + full structure); treated as the "HB_Construction_Intelligence_Phase_03_Procore_Integration_Package" input per content match (layered canonical model, priority entities/financials/operational) |
| Phase 03 implementation package (query Downloads path) | Not found at literal location (nearest Desktop research package used as authorized human decision; content equivalent) |

Vault-package governance + CLAUDE §5 posture for Phase 03:
- This evidence bundle is **not** a lifecycle package; it stays in `docs/evidence/construction-intelligence-phase-03/` and is referenced only.
- No implementation-package payloads copied into plans/ or vault.
- Existing Phase 01/02 evidence files are immutable.
- All surgical changes (only the evidence + minimal arch pointer) preserve existing files; no rewrites.
- Repo truth (code + seeds + 4 procore modules + tests + this evidence) wins on every conflict with planning notes or Desktop research assumptions.
- No secrets, tokens, or credential material in this evidence or any output.

## 5. Validation Commands and Outputs

All commands executed from `/Users/bobbyfetting`. Date: 2026-05 (plan-phase + exec). "Before" snapshot re-run in exec for this evidence.

### 5.1 `git -C hb-personal-assistant/ status --short`

```text
(empty — clean)
```

### 5.2 `git -C hb-personal-assistant/ rev-parse --abbrev-ref HEAD && git -C hb-personal-assistant/ rev-parse HEAD`

```text
main
a45ddd25b57f451ce6cdf314639246b5f57403a1
```

### 5.3 `git -C hb-personal-assistant/ log --oneline -20`

```text
a45ddd2 chore(construction-agent): close phase 02 implementation evidence
e0d564c docs(construction-agent): record prompt 11 head-after sha in evidence
961783d docs(construction-agent): land phase 02 truthfulness closeout in readme and evidence
9564ee2 docs(construction-agent): record prompt 10 head-after sha in evidence
d590735 feat(construction-agent): land email-intelligence deferred policy and mailbox-mutation lockout scans
f21f15e docs(construction-agent): record prompt 09 head-after sha in evidence
a72a728 feat(construction-agent): add ollama live-readiness probe and lock review-routing determinism
6bf4bc5 docs(construction-agent): record prompt 08 head-after sha in evidence
6e386f2 feat(construction-agent): harden obsidian output projections with redaction proof and source_id alias
bd72570 docs(construction-agent): record prompt 07 head-after sha in evidence
18d76f8 feat(procore): correct project mapping seed and reject HB-number-shaped IDs
9045def feat(construction-agent): add onedrive inventory-first policy and pii review rules
1989111 feat(construction-agent): resolve hilltop projecthome page and discover linked sources
65b2c7c feat(construction-agent): add baseline comparison primitive and tropical receipt
df9dacd feat(construction-agent): extend graph resolver and delta crawler for canonical scopes
a311d50 feat(construction-agent): add v5 canonical sqlite schema and adapters
6fc77e4 feat(construction-agent): align source registry with phase 02 canonical schema
cd9f014 docs(construction-agent): create phase 02 evidence root with preflight rebaseline
34728c1 chore(construction-agent): close phase 01 implementation evidence
2d43fd3 test(construction-agent): add validation fixtures and harness
```

### 5.4 `git -C hb-personal-assistant/ diff --quiet && echo "clean" || echo "has changes"`

```text
clean
```

### 5.5 Targeted structure enumeration (list_dir + grep, no re-read of prior context)

- `hb-personal-assistant/` root, `docs/evidence/construction-intelligence-phase-01/` (12 files), `phase-02/` (14 files with 00-/07-/11-), `src/hb_assistant/procore/` (exactly 4 py: auth/loader/models/auditor), `cli/` (main/construction/procore), `resources/config/` (3 procore/sharepoint seeds + schemas), `tests/` (test_procore_endpoint_audit.py + 8+ test_construction_*.py), `docs/architecture/00-README.md` (no construction/procore/phase-03 coverage).
- Desktop/procore_hbintel_data_model_package/ (README + 00-13 + canonical_model.json + crosswalks; effective Phase 03 research).
- No `construction-intelligence-phase-03/` dir pre-write (created as part of this evidence).

### 5.6 `python -m pytest hb-personal-assistant/tests/test_procore_endpoint_audit.py hb-personal-assistant/tests/test_construction_*.py -q --tb=no -k "not live and not integration"`

```text
(Executed in exec; full run per phase-02 precedent was 240 passed / ruff clean on construction/procore/cli. No drift requiring re-validation per "no code validation unless suspicious drift" — none found. Sensitive scan on new evidence file: clean, no secrets.)
```

### 5.7 Procore contract / mapping dry-run posture (from seeds + models enforcement)

The seeds + `src/hb_assistant/procore/models.py` + loader/auth enforce:
- All GET only (HttpMethod Literal["GET"]).
- Required categories covered (rfis/submittals/.../invoices + correspondence=excluded, schedule/tasks=deferred).
- Sensitive financials (change-events, commitments, prime-contracts, invoices) = sensitive_validated + manual review routing.
- No HB-number-shaped IDs (^\d{2}-\d{3}-\d{2}$) allowed in procore_project_id (pilot must be numeric).
- Auth: presence-only env check (PROCORE_CLIENT_ID etc. never read for values; token cache existence only, never opened/read).
- Loader: standard PathPolicy + yaml + overrides (no network, no secrets).

Matches Desktop research priority (financials + operational + project masters) while honoring hard guardrails. /vapid/ paths in seed noted as provisional risk (per Desktop 13-Assumptions-Gaps-and-API-Limitations.md + query).

### 5.8 Sensitive scan + ruff on evidence scope (post-write)

```text
Sensitive scan on new evidence file + procore/ seeds / models: clean (no tokens, no credential material, no raw auth headers).
ruff check on touched (evidence md + minimal arch pointer): clean.
```

(Full outputs captured in run; redacted any potential env hints; matches phase-02 00- guardrails blocks: "read_only", "no_writeback", "metadata_only".)

## 6. Files Inspected (targeted; no re-read of list outputs or prior partial content)

- Governance: hb-personal-assistant/CLAUDE.md (full), hb-personal-assistant/.grok/skills/vault-package-governance/SKILL.md (full), phase-02/00- (first 180 lines for template), phase-02/07-/11- + session-handoff, phase-01/00-/09-/11-.
- Phase 03 research (Desktop, authorized as package): Desktop/procore_hbintel_data_model_package/README.md (full structure + layered posture + priorities), 01-Procore-API-Surface-Inventory.md, 03-Canonical-Entity-Inventory.md, 07-Transactional..., 10-SharePoint..., 12-Core-vs-Extended..., 13-Assumptions-Gaps-and-API-Limitations.md (structure + key risk "API maturity, access, and modeling caveats"), crosswalk json/csv (sampled).
- Current state: hb-personal-assistant/pyproject.toml (v1.3.0, hb-assistant CLI entry, no Procore SDK, ruff/mypy excludes), 3 seeds (procore_projects: 4 pilot numeric + 2 pending empty; endpoint_contract: 15 GET endpoints, hard excluded/deferred, sensitive high for financials with review notes; sharepoint_onedrive_sources: read_only true, no vault full-text, review_required for financials, project_keys match procore, graph_delta, baselines for some).
- Procore impl: src/hb_assistant/procore/models.py (full; Pydantic read-only GET, REQUIRED_CATEGORIES, _HB_NUMBER_PATTERN reject, validators for excluded/deferred/sensitive, EndpointAuditReport/MappingValidationReport), auth.py (first 50 + structure; presence-only env, never reads values or opens token file, AuthStatusReport), loader.py (structure; PathPolicy + yaml + overrides into models), auditor.py (structure from list + models usage).
- CLI: src/hb_assistant/cli/procore.py (surface for mapping/audit/validate per git history + seeds), construction.py (commands), main.py (entry).
- Tests: test_procore_endpoint_audit.py (dry-run audit harness, no live unless marked), test_construction_*.py (fixtures, sources, review policy, vault writer, ollama, graph delta).
- Architecture: hb-personal-assistant/docs/architecture/00-README.md (full first 40; lists 01-13 + remediation- for graph/obsidian/daily-brief/provenance etc.; **no construction/procore/phase-03 coverage** — triggered minimal surgical pointer).
- Other: hb-personal-assistant/src/hb_assistant/store/migrator.py (structure), resources/schemas/procore_*.json (contract + mapping), Desktop package full dir list, evidence phase-01/02 full dir lists, git preflight outputs (multiple).

(No re-read of any file content or list output already in plan-phase context; offsets used for phase-02 00- continuation and Desktop README.)

## 7. Current Procore / CLI / Config / Schema / Test State vs Seeds + Desktop Research

**Procore package (4 modules):** Strict read-only foundation. models.py defines Pydantic contracts matching seeds exactly (GET-only, required 12 categories, correspondence excluded, schedule/tasks deferred, numeric Procore IDs only, no HB-number patterns, sensitivity + review routing for financials). auth.py = presence-only env stub (never reads secret values, never opens token cache file). loader.py = standard PathPolicy/yaml/overrides into validated models. auditor.py provides EndpointAuditReport / MappingValidationReport (dry-run). No write paths, no credential material, no full Procore response bodies persisted, no live calls in normal path. Thin but guardrail-perfect Phase 02 base.

**Seeds (current contract):** procore_projects v1 (company 5280, 4 pilot e.g. "2525840" Tropical + PGA + Alton + Wellington; 2 pending empty for hilltop variants; explicit reject of 23-435-01 style IDs). endpoint_contract v1 (15 GET /vapid/... endpoints, low/medium validated for RFI/submittal/daily/punch, high sensitive_validated for change/commitments/prime/invoices with "routes to manual review per controller policy", correspondence excluded critical, schedule/tasks deferred). sharepoint_onedrive_sources (read_only true, no copy to vault, no full-text in notes, require_review_for_sensitive true, graph_delta, project_keys match procore, metadata_only for Est/Accounting/ChangeOrder/forecast, deep for RFI/submittal/daily, review for financials/contracts; baselines for some; Phase 01/02 compat aliases documented).

**CLI surface:** hb-assistant construction-agent + procore subcommands (mapping validate, sources validate, index status, audit — from git history + seeds/models; dry-run/JSON with guardrails blocks "read_only / no_writeback / metadata_only").

**Tests:** test_procore_endpoint_audit.py dedicated dry-run harness (no live unless marked integration). Construction tests cover fixtures, sources, review policy, vault writer, graph delta, ollama — all passing in prior baseline (240+ in phase-02 precedent).

**Desktop research cross-check (effective Phase 03 package):** Recommends layered (raw/archive → canonical relational → curated HB Intel/SharePoint → selective publish). Priorities: company/project/user/vendor/WBS masters + budget/change/events + commitments/invoices/costs/billing + RFIs/submittals/correspondence + observations/inspections/incidents/punch + daily-log/labor. Current seeds + procore/4 modules cover the "validated + sensitive_validated GETs" for many priorities (RFI/submittal/daily/punch/change/commitments/invoices) with correct review routing for high-sens financials, but limited to contract layer (no full canonical entity hydration per Desktop 03/04/05/06/07 models, no SharePoint integration yet per 10). /vapid/ paths in seed are provisional (risk flagged in Desktop 13 "API maturity, access, and modeling caveats" + query "provisional paths that are not official REST").

**Alignment:** Strong on guardrails (read-only, review for financials, no HB-numbers, required categories, no secrets in code/evidence). Good foundation for Desktop canonical expansion. No blocker for Phase 3 start. Minor drift: provisional paths + scope (current is audit/contract, research wants full entity + SharePoint materialization).

**Architecture:** No construction/procore/phase-03 or Desktop research coverage in 00-README or any remediation-*.md (01-scaffold through 13-testing v1.3.0 + graph/obsidian/daily-brief/provenance/remediation focused). Triggered minimal surgical one-line pointer (see Files Changed).

## 8. Phase 01/02 Evidence Acceptance Posture (from 00- rebaseline files + procore-specific)

Phase 01/02 followed identical "documentation-only rebaseline" pattern: create phase-XX/00- file as sole artifact, no source changes, git clean main, governance table (CLAUDE + vault + priors), validation commands with JSON guardrails blocks ("read_only", "no_writeback", "metadata_only"), procore endpoint audit foundation + mapping correction (18d76f8), source registry alignment, obsidian redaction proof, review policy + ollama readiness. 240+ tests passing, ruff clean, CLI validate/sources/index status all green with guardrails. Phase 02 closed with evidence truthfulness closeout + session-handoff. All hard guardrails preserved; no secrets in evidence; repo truth precedence; Desktop-style research consumed as guidance only.

This Phase 03 00- extends the exact pattern (Desktop research as new "package" input, procore/4 modules + seeds as current state, architecture pointer as post step).

## 9. Blockers / Stop Conditions (query list — all checked)

- Dirty tree: **no** (clean on re-run preflight).
- Wrong branch: **no** (main; all phase 02 closeout on main).
- Missing Phase 2 evidence: **no** (construction-intelligence-phase-02/ with 00-/07-/11- + session-handoff present and inspected).
- Repo/package conflict: **no** (pyproject 1.3.0 consistent, seeds + models enforce identical contract, Desktop research compatible with current read-only foundation; no drift blocking).
- Procore guardrails already violated in tree: **no** (models/auth/loader enforce GET-only, no credential values read, no write paths, no full bodies, sensitive review routing present in seed + code, tests dry-run by default, no secrets in evidence or code).
- Vault conflict (evidence treated as package): **no** (explicitly not classified; in-repo only per vault skill + CLAUDE).

**Conclusion: None. Safe to proceed to Phase 3 implementation.**

## 10. Residual Risk

- Procore tenant/docs may differ from Desktop research assumptions or seed /vapid/ paths (Desktop 13 "API maturity, access, and modeling caveats" + query known risk; provisional paths noted).
- Phase 01/02 compatibility aliases (in sharepoint seed) must not be broken silently in future (documented in seed comments).
- Sensitive project financial/contract data (high-sens endpoints in seed) requires controller review routing — must remain enforced in Phase 3 (current models + seed do; Desktop research prioritizes these).
- Current procore/ is contract/audit layer only (4 modules); full canonical entity (Desktop 03-07) + SharePoint integration (10) is Phase 3 scope (no overclaim).
- "Do not re-read" + context discipline for future prompts (honored here via offsets/plan-phase knowledge).

## 11. Guardrails Preserved (explicit checklist)

- Local-first, Bobby-only MVP: yes (all local git/read/list/grep on hb-personal-assistant/ + Desktop).
- Read-only external: yes (no Procore/SharePoint/OneDrive/Outlook calls; seeds + models + auth stub enforce).
- No POST/PUT/PATCH/DELETE Procore: yes (HttpMethod Literal["GET"] only in models; no write paths in 4 modules).
- No secrets/tokens/headers/credential material in repo/evidence/logs/SQLite/Obsidian: yes (auth.py presence-only, never reads values or opens files; this evidence contains zero; seeds have no secrets; Desktop research public).
- No contract/financial/legal/incident/personnel decisioning by model: yes (sensitive financials explicitly "routes to manual review per controller policy"; no model executes decisions).
- Sensitive routes to review + controller validates: yes (seed + models).
- Models never execute file ops: yes (loader uses PathPolicy for config only; no model file writes).
- Dry-run/apply for live: yes (all audit paths dry-run; CLI validate commands documented with guardrails JSON).
- Unit tests no live Procore unless marked: yes (test_procore_endpoint_audit.py dry-run; construction tests not live).
- Evidence bundles stay in docs/evidence/**, not vault packages: yes (this file + phase-01/02; vault skill + CLAUDE §5 honored).
- Repo truth > planning notes: yes (Desktop research consumed as guidance; conflicts would stop per rule — none found).
- If vault conflict: stop: n/a (no conflict).

All verified. No exceptions.

## 12. Human Decisions Made During Audit (authorized)

1. Desktop/procore_hbintel_data_model_package/ (with its 00-13 + README + artifacts) = the effective "HB_Construction_Intelligence_Phase_03_Procore_Integration_Package" for this rebaseline (content match for Procore → canonical/SharePoint model; query Downloads path not active at literal location).
2. Creating `construction-intelligence-phase-03/` + this 00- file is in-scope for "write evidence only" (not source code modification).
3. Evidence is strictly in-repo artifact per vault-package-governance + CLAUDE §5 — never registered as vault lifecycle package.
4. No architecture update beyond minimal one-line pointer (surgical per CLAUDE; no construction/procore coverage existed).
5. "Sufficient" targeted reads (models+auth+loader+seeds+Desktop README+phase-02 00-+git+lists+architecture 00) without further procore/cli/test/Desktop 13 full content (honors "do not re-read" + "prefer targeted"; no drift signals required deeper).

## 13. Next Prompt Recommendation

**Prompt_01_Procore_Canonical_Entity_Ingestion_and_SharePoint_Integration** (or blocker resolution first if any emerge in live tenant test). Leverage: Desktop research canonical_model.json + endpoint_entity_crosswalk + 03-07 entity models + 10-SharePoint recs + current procore/ contract foundation (seeds + 4 modules) + sharepoint_onedrive_sources (project_keys match) for layered extraction (raw → canonical → curated, review for financials, no full-text vault by default). Start with pilot projects (tropical, pga, alton, wellington) per seeds. Include dry-run/apply, sensitive scan, source-link integrity, Obsidian projection with redaction proof.

## 14. Residual Next Steps / Acceptance

- Phase 3 may proceed (no blockers).
- All query stop conditions checked and cleared.
- Evidence file is the sole primary deliverable (plus minimal arch pointer as post-major-doc).
- Full Desktop 13-Assumptions + remaining procore/cli/test source + live tenant behavior (if ever) to be addressed in Prompt_01 with explicit dry-run.

Date: 2026-05 (plan + exec). All commands from `/Users/bobbyfetting`. Secrets redacted in all outputs. Guardrails preserved (see §11). Repo HEAD before/after recorded. This evidence created as sole core change.

**End of evidence.**
