# Phase 07D · Prompt 00 — Repo-Truth Audit & 07C Gap Inventory (Rebaseline)

**Generated (UTC):** 2026-06-01
**Observed HEAD:** `733ffedae071ce6a766a33fcd9233205364b8013`
**Package version:** `1.3.0` · **Schema version:** `24` (`LATEST_SCHEMA_VERSION = 24`)
**Verdict:** Repo truth re-baselined at observed HEAD. 07D meeting-prep/intelligence build is **BLOCKED**
(honest closeout preserved). Prompt 01 (07C remediation preflight) **may proceed**.

This file is an **audit/rebaseline artifact only**. Prompt 00 introduces no schema migration, no new CLI
surface, no resource/seed change, and no runtime behavior change. It records the live repo state at HEAD,
reconciles the 07C closeout-evidence SHA staleness (gap **G9**), and classifies every G1–G10 blocker so the
next prompt knows what is allowed to run.

---

## 1. Repo-truth preflight

| Fact | Value | Source |
|---|---|---|
| `git rev-parse HEAD` | `733ffedae071ce6a766a33fcd9233205364b8013` | git |
| `git status --short` | clean except untracked `.claude/` (local agent config, out of scope) | git |
| Python (venv default) | `3.14.5` (a `python3.12` interpreter is also present in `.venv`; CLAUDE.md requires 3.12+) | `.venv/bin/python --version` |
| `hb-assistant --version` | `1.3.0` | CLI |
| Package version | `1.3.0` | `pyproject.toml` `version` |
| Schema version (code) | `24` | `src/hb_assistant/store/migrator.py` `LATEST_SCHEMA_VERSION` |
| Schema version (runtime) | `24` | `construction-agent validate --json` → `schema_version=24` |
| Evidence folders | `73` entries under `docs/evidence/`; the 07D folder `construction-intelligence-phase-07d-cross-source-meeting-prep/` is **created by this prompt** | `ls docs/evidence/` |

### 1.1 Ancestry confirmation

All three requested baseline commits are ancestors of observed HEAD (`git merge-base --is-ancestor`):

| Commit | Role | Distance from HEAD | Ancestor? |
|---|---|---|---|
| `733ffedae071ce6a766a33fcd9233205364b8013` | **07C closeout = current HEAD** | 0 | yes (HEAD itself) |
| `748ed7e6519ada0a74d09376f2d2fe353627ac2b` | 07B closeout | 14 commits | yes |
| `3cf1652bf55303ceea25b2bbc6b5b1785111a335` | 07A closeout | 29 commits | yes |

Lineage is contiguous: 07A (`3cf1652`) → 07B (`748ed7e`) → 07C (`733ffed` = HEAD). No branch or worktree was
created; the audit ran against the live working tree in place.

---

## 2. Validation matrix (observed HEAD `733ffed`, schema `24`)

Every command was executed in the project venv at HEAD `733ffed`. Excerpts are **structural only** — SHAs,
schema version, counts, gate identifiers, exit codes — **no raw email/document/calendar content, no signed or
download URLs, no tokens, no secrets**.

| # | Command | Exit | Safe redacted excerpt |
|---|---|---|---|
| 1 | `python -m compileall src tests` | `0` | byte-compiled clean; no errors |
| 2 | `ruff check .` | `0` | `All checks passed!` |
| 3 | `mypy src` | `0` | `Success: no issues found in 176 source files` |
| 4 | `pytest -m "not live and not integration and not manual"` | `0` | **2064 passed** (collection sum = 2064; matches 07C closeout count) |
| 5 | `construction-agent validate --json` | `0` | `ok` 4/4 — schema `24`; source_registry `6 projects, 14 sources`; review_rules `25 rules, threshold=0.7`; model_routing `llama3.2:1b` |
| 6 | `procore validate --json` | `0` | `ok=true`; summary `28/28 passed, 0 failed` |
| 7 | `graph files status --json` | `0` | `ok=true`; delegated auth `mode=delegated`, `available=true` |
| 8 | `graph files no-writeback-proof --json` | `0` | `ok=true`; `static_scan.files_scanned=41`, `mutation_method_calls_found=0`; `guard_self_test.passed=true` (`read_paths_allowed=24`, `mutation_attempts_blocked=19`, `anomalies=[]`); `permission_tightening=deferred` |
| 9 | `graph calendar status --json` | `0` | `ok=true`; `calendar_read_capability_present=true`; `write_capable_calendar_scopes_present=["Calendars.ReadWrite.Shared"]` (read-only at adapter); `upn=bfetting@hedrickbrothers.com` |
| 10 | `graph mail status --json` | `0` | `ok=true`; `mail_read_scope_present=true`; `forbidden_mail_scopes_requested=[]` |
| 11 | `construction-agent data-quality gates --json` | `0` | `repo_sha=733ffed…`, `schema_version=24`; **21 gates** (15 pass / 3 warning / 1 not_applicable / 2 deferred_not_blocking); `meeting_prep_readiness_claim=blocked` |
| 12 | `construction-agent data-quality no-writeback-proof --json` | `0` | `proof_passed=true`, `repo_sha=733ffed…`, `schema=24`; scanned modules 6 (07A) + 10 (07B) + 9 (07C); `no_live_call_performed=true`; `no_raw_values_persisted=true` |
| 13 | `construction-agent data-quality table-inventory --json` | `0` | `repo_sha=733ffed…`, `schema=24`; `table_count=106` |

### 2.1 Live runtime SHA/schema stamping (proof of runtime correctness)

The three persistence/proof reports stamp the **correct** observed HEAD and schema:

```
data-quality gates           → repo_sha=733ffedae071…  schema_version=24
data-quality no-writeback     → repo_sha=733ffedae071…  schema_version=24  proof_passed=true
data-quality table-inventory  → repo_sha=733ffedae071…  schema_version=24  table_count=106
```

### 2.2 Gate map (21 gates @ HEAD)

| Gate | Status | | Gate | Status |
|---|---|---|---|---|
| project_identity_coverage | not_applicable | | document_relationship_population_status | pass |
| source_record_map_coverage | warning | | document_source_scope_compliance | **deferred_not_blocking** |
| deterministic_orphan_rate | pass | | document_intelligence_safety_scan | pass |
| candidate_orphan_rate | pass | | financial_amount_parseability | warning |
| calendar_population_status | pass | | financial_currency_completeness | warning |
| email_classifier_persistence_status | pass | | review_required_routing_presence | **deferred_not_blocking** |
| email_thread_summary_population_status | pass | | raw_content_leakage_scan | pass |
| meeting_email_candidate_population_status | pass | | external_writeback_scan | pass |
| document_card_population_status | pass | | query_latency_p95 | pass |
| document_classification_coverage | pass | | | |
| document_project_match_coverage | pass | | | |
| document_extraction_eligibility_status | pass | | | |

**07D meeting-prep readiness** (from `phase_go_nogo.07D`):

```
meeting_prep_readiness.ready             = false
meeting_prep_readiness.blocked_by        = ["document_source_scope_compliance",
                                            "review_required_routing_presence"]
meeting_prep_readiness.auto_readiness_allowed = false
relationship_quality_ready               = true   (deterministic relationships only)
```

The two `warning` financial gates and the `warning` source_record_map gate are non-blocking and do not gate
07D; the `not_applicable` project_identity gate reflects no new identity work at this point. No gate is in a
hard-`fail` state.

---

## 3. Inventory (affected tables, commands, tests, evidence)

### 3.1 Tables — none changed by this prompt

Schema stays at **V24**. The 07C document-intelligence surface (`construction_document_*` cards /
classification / project-match / relationship-candidates / intelligence-previews / projection-runs, each with
hard `CHECK(… = 0)` guard columns for `raw_document_text_persisted`, `raw_payload_persisted`,
`signed_url_persisted`, `download_url_persisted`, `source_file_copied_to_vault`, `raw_prompt_persisted`,
`raw_response_persisted`, `external_writeback_performed`) is present and unchanged. `table-inventory` reports
**106** tracked tables. No migration is added in Prompt 00 (relationship/meeting-prep schema is a later 07D
prompt's responsibility — see G3/G5/G6 below).

### 3.2 Command surface — already present, unchanged

- `construction-agent data-quality`: `project-coverage`, `source-record-map`, `relationships`, `marts`,
  `obsidian`, `gates`, `no-writeback-proof`, `table-inventory` (`src/hb_assistant/cli/construction.py`).
- `graph files`: `status`, `no-writeback-proof`, `scope-compliance`, plus the 07C document-intelligence
  pipeline (`materialize-document-cards`, `classify-document-cards`, `match-document-projects`,
  `evaluate-extraction-eligibility`, `build-document-relationships`, `build-document-previews`,
  `document-obsidian`) (`src/hb_assistant/cli/graph.py`).
- `graph mail status`, `graph calendar status` / `calendar index` (`src/hb_assistant/cli/graph.py`).
- Gate logic + identifiers: `src/hb_assistant/construction/data_quality/gates.py` (`_CORE_GATE_NAMES`,
  `evaluate_data_quality_gates`).

**07D CLI surfaces do not yet exist** (relationships build/status, meeting-prep build/status, issue-history,
risk-digest, aging-exposure, cross-source Obsidian, 07D gates, 07D no-writeback proof) — see **G5**.

### 3.3 Tests — existing suite is the regression guard (no new tests added)

Prompt 00 adds no feature code, so no new unit tests are introduced. The existing **2064-test** subset (exit 0)
covers the surfaces this audit touches, including: `tests/test_data_quality_gates.py`,
`tests/test_data_quality_safety_proof.py`, `tests/test_data_quality_table_inventory.py`,
`tests/test_data_quality_document_gates.py`, the `tests/test_document_*` set, the `tests/test_graph_files_*`
set, and `tests/test_graph_{mail,calendar}_*`. The prompt's success/blocked/review-required/no-raw-content/
idempotency test list describes **07D feature behavior** and is deferred to the prompts that build those
features (G3–G6).

### 3.4 07C evidence file set (read; not modified)

`docs/evidence/construction-intelligence-phase-07c-document-intelligence/` holds Prompts 00–13 plus
`phase-07d-08a-08b-handoff.md` (15 files). These are immutable closeout records and are **not** rewritten here
(see §4).

---

## 4. G9 — closeout-evidence SHA staleness, reconciled here

**Finding.** The static 07C closeout markdown records a different repo_sha than the audited closeout commit:

| 07C evidence file | Recorded `repo_sha` | Note |
|---|---|---|
| `13-final-validation-closeout.md` (line 6) | `b65f3c085fac8d811c11f9ffb29158455f77db03` | closeout-doc SHA |
| `phase-07d-08a-08b-handoff.md` (line 4) | `b65f3c085fac8d811c11f9ffb29158455f77db03` | matches closeout doc |
| `12-no-writeback-…-proof.md` (line 6) | `778aa7a54224f7ce0e1683d0d6a493d70c395549` | safety-proof run SHA |

The audited 07C closeout commit is **`733ffed`** (this HEAD). `b65f3c0` and `778aa7a` are **ancestors** of
`733ffed` — they are the commits at which those individual evidence files were generated, before the final
docs/closeout commit (`733ffed`) landed. This is a **docs-after-evidence ordering artifact, not a defect**.

**Why it does not compromise truth.** The *live runtime* stamps the correct HEAD: `data-quality gates`,
`no-writeback-proof`, and `table-inventory` all emit `repo_sha=733ffedae071…` at this HEAD (§2.1). The
staleness is confined to a handful of static markdown lines written mid-sequence.

**Resolution.** This file is the **rebaseline at observed HEAD `733ffed`**. The historical 07C evidence files
are left **unmodified** (immutable closeout records); the discrepancy is annotated here rather than rewritten,
preserving the audit trail. No 07C conclusion changes — 07C remains a closed document-intelligence layer with
07D honestly blocked.

---

## 5. Gap classification (G1–G10) at repo truth

| ID | Classification | Repo-truth status at HEAD `733ffed` | Disposition |
|---|---|---|---|
| **G1** | Must fix before 07D build | `document_source_scope_compliance = deferred_not_blocking`; the live source registry has a source not scope-compliant under the document-source policy (a OneDrive scope lacking a formal selected-folder allowlist). Per user clarification, an explicit OneDrive allowlist must be able to mean **all folders**. | **Prompt 01** — add a compliant all-folders/root-and-all-nested allowlist path; keep ambiguous/implicit OneDrive scope blocked. |
| **G2** | Must fix before 07D build | `review_required_routing_presence = deferred_not_blocking`. The gate must reconcile review-required evidence across relationship, document, email, calendar, and Procore queues before any summary is trusted. | **Prompt 01** — normalize review-required routing across all review sources. |
| **G3** | Implement inside 07D | No unified cross-source relationship substrate; candidates are fragmented across document/email/calendar/Procore edges + source-record-map tables. | 07D relationship-substrate prompt (additive schema). |
| **G4** | Implement inside 07D | Document→email / document→calendar arms deferred: `calendar_event_index.project_key` is NULL and `email_messages` has no `project_key` alignment. | 07D normalization/matching before meeting prep. |
| **G5** | Implement inside 07D | 07D CLI surfaces absent (relationships, meeting-prep, issue-history, risk-digest, aging-exposure, cross-source Obsidian, 07D gates, 07D no-writeback proof). | 07D CLI prompts. |
| **G6** | Implement inside 07D | No meeting-prep brief, project issue-history, risk digest, aging/exposure, or source-evidence-trail model exists. | 07D materialization prompts. |
| **G7** | Implement inside 07D | 07C Obsidian document output was **preview/dry-run only**; the real vault was not written. Do not assume vault notes exist unless validated. | 07D keeps dry-run default; `--apply` only when validated. |
| **G8** | Guardrail (inside 07D) | The 06A `construction_drive_item_inventory` raw-staging layer intentionally stores raw file names/paths/web links. | 07D outputs must read only redacted/hashed/card-level surfaces or explicitly fenced references — never the raw staging layer. |
| **G9** | Remediate in Prompt 00 evidence | **Done here** (§4): runtime stamps `733ffed`; static 07C markdown recorded `b65f3c0`. Rebaselined at observed HEAD; historical evidence left immutable. | **Resolved.** |
| **G10** | Defer to 08C | Financial records can supply exposure indicators, but forecast/financial determination remains blocked until a dedicated financial readiness phase. | Out of 07D scope. |

---

## 6. No-raw-content / no-writeback attestation (this artifact)

This evidence file persists **only** structural metadata: commit SHAs, schema/package versions, integer
counts, gate identifiers and statuses, command exit codes, and a UPN that is the operator's own published
work identity (already present throughout the repo's status reports). It contains:

- **No** raw email body, raw document text, or raw calendar body/location/attendee detail.
- **No** signed URL, `@microsoft.graph.downloadUrl`, raw delta link, token, secret, or PEM.
- **No** raw prompt or raw model response.
- **No** external-system writeback, mutation, scope change, or write-scope request — the audit ran read-only;
  `external_writeback_scan = pass`, `raw_content_leakage_scan = pass`, and the no-writeback proofs returned
  `proof_passed=true` / `no_raw_values_persisted=true` (§2).

No weak-heuristic, model-proposed, sensitive, legal, contractual, claim, personnel, safety, incident, injury,
financial, or high-impact relationship is promoted by this prompt. Outputs are advisory project-intelligence
aids only.

---

## 7. Handoff to Prompt 01

- **What changed:** one new evidence file (this rebaseline); a README "Repository Status" Phase 07D
  in-progress entry; a one-line CLAUDE.md schema reference fix (`V1…V19` → `V1…V24`). No code, schema, CLI,
  resource, or 07C evidence change.
- **Gates:** all 12 validation commands exit `0`; `pytest` 2064 passed; data-quality gates 15 pass / 3 warning
  / 1 n/a / 2 deferred_not_blocking; no hard failures. The two `deferred_not_blocking` gates
  (`document_source_scope_compliance`, `review_required_routing_presence`) are the standing 07D blockers.
- **Readiness (honest):** 07D meeting-prep/intelligence build is **BLOCKED** — `meeting_prep_readiness.ready
  = false`, `auto_readiness_allowed = false`. Not overstated.
- **Next prompt allowed?** **Yes — Prompt 01 (07C remediation preflight) may proceed** to remediate G1 and G2.
  07D relationship normalization and meeting-prep materialization (G3–G8) remain gated until G1/G2 pass.
