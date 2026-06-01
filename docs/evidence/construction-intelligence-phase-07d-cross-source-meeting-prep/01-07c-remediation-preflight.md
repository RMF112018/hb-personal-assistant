# Phase 07D · Prompt 01 — 07C Remediation Preflight (OneDrive all-folders + review-routing)

**Generated (UTC):** 2026-06-01
**Validation HEAD (pre-commit):** `65760e54bae0859fe8b7ffc85f87cfd3dc1ec9c8` (Prompt 00 closeout)
**Package version:** `1.3.0` · **Schema version:** `24` (no migration — config/policy/Python only)
**Verdict:** Blockers **G1** (`document_source_scope_compliance`) and **G2**
(`review_required_routing_presence`) are **resolved**: both gates flip to `pass`. Prompt 02 (relationship
schema & contracts) **may proceed**.

This prompt is additive and read-only. No SQLite migration, no new CLI command, no external writeback. The
explicit OneDrive all-folders path is an operator opt-in; implicit root-wide indexing stays blocked.

---

## 1. Repo-truth preflight

| Fact | Value |
|---|---|
| `git rev-parse HEAD` (pre-commit) | `65760e54bae0859fe8b7ffc85f87cfd3dc1ec9c8` |
| `git status --short` | intended edits (models/policy/evaluator/gates/seeds/tests/docs) + new evidence/arch; untracked `.claude/` (out of scope) |
| `python --version` | venv default `3.14.5` (3.12 also present; CLAUDE.md requires 3.12+) |
| `hb-assistant --version` | `1.3.0` |
| Package version | `1.3.0` (`pyproject.toml`) |
| Schema version | `24` (`migrator.py LATEST_SCHEMA_VERSION`; runtime `construction-agent validate` → `schema_version=24`) |
| Evidence folders | 73+ under `docs/evidence/`; this is the 2nd file in `construction-intelligence-phase-07d-cross-source-meeting-prep/` (after `00-repo-truth-rebaseline.md`) |

### Ancestry confirmation (`git merge-base --is-ancestor`)

`65760e5` (Prompt 00) · `733ffed` (07C closeout) · `748ed7e` (07B closeout) · `3cf1652` (07A closeout) —
**all ancestors of HEAD**. Lineage contiguous; no branch or worktree created.

---

## 2. Change set (smallest additive set)

| File | Change |
|---|---|
| `construction/config/models.py` | `SourceLocation.allow_all_folders: bool = False` (fail-closed opt-in) |
| `policy/document_source_policy.py` | `OneDriveScopePolicy.allow_explicit_all_folders: bool = True`; Literal locks unchanged |
| `resources/config/document_source_policy.seed.yaml` | `onedrive.allow_explicit_all_folders: true`; `intended_scope: selected_folders_or_explicit_all_folders` |
| `construction/document/source_scope.py` | local `_ONEDRIVE_ALL_FOLDERS_ROOT_KINDS` (canonical + legacy compat roots, NOT the shared inventory-first set); explicit all-folders branch; `onedrive_scope_breakdown` |
| `resources/config/sharepoint_onedrive_sources.seed.yaml` | `allow_all_folders: true` on the 3 canonical OneDrive roots + the legacy compat duplicate `bobby-onedrive` |
| `construction/data_quality/gates.py` | scope gate attaches `onedrive_scope_breakdown`; review-routing gate reconciles across queues + attaches `review_routing_breakdown` |
| tests | `test_document_source_scope.py` (4-path + legacy-compat + policy-disabled + idempotency), `test_data_quality_document_gates.py` (review-routing pass/defer/idempotent + scope breakdown), `test_graph_files_scope_compliance.py` (updated to post-remediation live state) |
| `docs/architecture/43-…` | architecture record |

**`bobby-onedrive` disposition (operator-directed):** a Phase 01 compat duplicate (kind `onedrive_personal`,
`resolution_status: pending`) of the approved `od_personal_bobby`. Per operator direction it is treated as a
legacy compat OneDrive root and made compliant via the explicit `allow_all_folders: true` opt-in — it is
**not** disabled, and no unrelated enabled-source-count test was changed. All-folder OneDrive indexing is
explicitly operator-approved. The legacy root kinds are recognized only by a **local** evaluator set; the
shared inventory-first scope set is untouched.

---

## 3. Before → after (G1 / G2)

| Signal | Before (Prompt 00) | After (this prompt) |
|---|---|---|
| `graph files scope-compliance` → `all_compliant` | `false` (OneDrive roots blocked) | **`true`** |
| OneDrive scope breakdown | n/a | `{all_folders_explicit_compliant: 4, selected_folders_compliant: 0, implicit_root_blocked: 0}` |
| `document_source_scope_compliance` gate | `deferred_not_blocking` | **`pass`** |
| `review_required_routing_presence` gate | `deferred_not_blocking` (relationship queue only) | **`pass`** — breakdown `{relationship_resolution_queue: 0, construction_document_cards: 283, construction_review_queue: 0, email_review_queue: 0, calendar_project_match_candidates: 8}` |
| Gate status tally (21 gates) | 15 pass / 3 warning / 1 n/a / 2 deferred | **17 pass / 3 warning / 1 n/a / 0 deferred** |
| `meeting_prep_readiness.ready` | `false`, blocked_by `[document_source_scope_compliance, review_required_routing_presence]` | **`true`, blocked_by `[]`** |
| `auto_readiness_allowed` | `false` | `false` (unchanged — 07D is never auto-claimed) |

**Honesty note.** `meeting_prep_readiness.ready=true` reflects the **current local SQLite state**, which has
the 07C document layer materialized (283 review-required cards, etc.); on an empty store the data-presence
gates defer exactly as before. This prompt owns G1/G2 only — it flips those two gates; the remaining
prerequisites already passed on live data. `auto_readiness_allowed` stays `false`, so readiness is reported,
never auto-asserted.

---

## 4. Validation matrix (venv @ HEAD `65760e5`, schema 24)

Excerpts are structural only — SHAs, schema, counts, gate names, exit codes. No raw content.

| # | Command | Exit | Safe excerpt |
|---|---|---|---|
| 1 | `python -m compileall src tests` | `0` | clean |
| 2 | `ruff check .` | `0` | `All checks passed!` |
| 3 | `mypy src` | `0` | `Success: no issues found in 176 source files` |
| 4 | `pytest -m "not live and not integration and not manual"` | `0` | **2072 passed** (2064 baseline + 8 new) |
| 5 | `construction-agent validate --json` | `0` | 4/4 — schema 24; `6 projects, 14 sources`; 25 review rules |
| 6 | `procore validate --json` | `0` | `28/28 passed` |
| 7 | `graph files status --json` | `0` | `ok=true`; delegated, available |
| 8 | `graph files scope-compliance --json` | `0` | `all_compliant=true`; 14/14 compliant; OneDrive breakdown `4 explicit / 0 blocked`; guardrails `onedrive_root_wide_allowed=false`, `onedrive_explicit_all_folders_allowed=true` |
| 9 | `graph files no-writeback-proof --json` | `0` | `ok=true`; `static_scan.files_scanned=41`, `mutation_method_calls_found=0`; `guard_self_test.passed=true`, `mutation_attempts_blocked=19` |
| 10 | `graph calendar status --json` | `0` | `ok=true` |
| 11 | `graph mail status --json` | `0` | `ok=true` |
| 12 | `construction-agent data-quality gates --json` | `0` | `repo_sha=65760e5`, schema 24; scope=`pass`, review-routing=`pass`; readiness ready=true / blocked_by=[] / auto=false |
| 13 | `construction-agent data-quality no-writeback-proof --json` | `0` | `proof_passed=true`; `no_raw_values_persisted=true`; `repo_sha=65760e5` |
| 14 | `construction-agent data-quality table-inventory --json` | `0` | schema 24; `table_count=106` (unchanged) |

`graph files scope-compliance` is added to the standing matrix for this and later 07D prompts.

---

## 5. No-raw-content / no-writeback attestation

- No SQLite migration; schema stays **V24** (`table_count=106` unchanged).
- `data-quality no-writeback-proof` `proof_passed=true`, `no_raw_values_persisted=true` — the changed
  `source_scope.py` is in the 07C scanned-module set; the changed `gates.py` is in the 07A scanned-module set;
  no new module was introduced.
- `graph files no-writeback-proof` `ok=true`, 0 mutation calls across 41 files.
- The review-routing gate issues only `COUNT(*)`; no raw email/document/calendar body, URL, token, or secret
  is read or persisted. This evidence file stores only SHAs, counts, gate identifiers, and exit codes.
- The OneDrive all-folders path is an explicit operator opt-in; implicit/ambiguous root-wide stays blocked.
  All document cards remain `review_required`; nothing is auto-promoted.

---

## 6. Disposition & handoff to Prompt 02

- **G1 resolved** — explicit OneDrive all-folders allowlist; live registry `all_compliant=true`;
  `document_source_scope_compliance=pass`. Implicit root-wide still fail-closed.
- **G2 resolved** — review-routing reconciled across the document/relationship/email/calendar review queues;
  `review_required_routing_presence=pass`.
- **Readiness (honest):** with the current local 07C data, `meeting_prep_readiness.ready=true`,
  `auto_readiness_allowed=false`. No prerequisite remains blocked. Not overstated.
- **Next prompt allowed?** **Yes — Prompt 02 (relationship schema & contracts) may proceed.** The remaining
  07D gaps (G3–G8: cross-source relationship substrate, document↔email/calendar normalization, 07D CLI
  surfaces, meeting-prep/issue-history/risk/aging models, dry-run Obsidian, 06A raw-staging fence) are 07D
  build work for the subsequent prompts. G10 (financial determination) stays deferred to 08C.
