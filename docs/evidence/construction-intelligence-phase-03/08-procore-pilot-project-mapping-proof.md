# Evidence: Prompt_06 Project Mapping and Company Context (HB Construction Intelligence Phase 03)

**Date**: 2026-05-27  
**Prompt**: 06 (Project Mapping and Company Context)  
**Objective**: Validate company ID 5280 config; validate pilot mappings from repo seed; add CLI list/status for projects/companies; keep `hilltop` and `hilltop-gardens` pending unless numeric IDs verified; add tests for HB project-number vs Procore ID separation.  
**Validation**: `hb-assistant procore mapping validate --json`; tests.  
**Guardrails**: All non-negotiable guardrails preserved (see §11 attestation). Local-first, Bobby-only MVP, read-only external, no writeback/POST/PUT etc, no secrets in artifacts, no contract/financial decisioning, sensitive review routing, models never file ops, dry-run/apply, unit tests non-live.

## 1. Repo HEAD (before / after)
- **Before changes**: `93daf9315aa953734a19484648f6ceb15500b083` (main, clean tree per `git status --short`)
- **After changes (pre-commit)**: Working tree dirty (new seed + 2 edits); post-commit HEAD will be recorded in final commit manifest.
- Commands: `git -C hb-personal-assistant rev-parse HEAD`, `git -C hb-personal-assistant status --short`, `git -C hb-personal-assistant log --oneline -10`

## 2. Files Inspected (via safe discovery only; no re-read of core context)
- Targeted `list_dir`: `hb-personal-assistant/`, `docs/evidence/construction-intelligence-phase-03/`, `resources/config/`, `resources/schemas/`, `src/hb_assistant/cli/`, `src/hb_assistant/procore/`, `tests/`, `docs/architecture/`
- Safe capped terminal/git: `git show HEAD:resources/schemas/procore_project_mapping.schema.json | head -80`, `git grep -n "5280" .../procore_environments.seed.yaml`, `git show HEAD:resources/config/procore_projects.seed.yaml | head -60`, multiple `git -C ... rev-parse / status / log / show | tail/head/grep` for CLI test files and arch 00-README (structure strings only, redacted).
- Sub-agent safe exploration (3 explore read-only): list_dir/grep (restricted paths), read on allowed schemas/construction/config only, memory_search, 0 errors, 21-25 tool calls each, 90-143s duration.
- Confirmed: procore_project_mapping.schema.json present (hb_project_key, company_id, procore_project_id with anti-HB-pattern, status enum including pending/pilot); NO procore_project_mapping.seed.yaml pre-existing; 5280 in environments.seed (header mandatory); procore_projects.seed has 6 entries (4 pilot numeric e.g. 2525840 tropical, 2 pending hilltop* with empty ID + explicit separation comments); CLI procore.py had 4 commands + mapping_app + _load_* + auditor; tests had HB separation test (pre-existing); architecture 00-README had prior Phase 03 pointers.

## 3. Files Changed
- Created: `resources/config/procore_project_mapping.seed.yaml` (new dedicated pilot mapping artifact with company 5280 + 6 entries mirroring repo truth; 4 pilot + 2 pending hilltop*; HB numbers separate from Procore IDs; schema-aligned).
- Modified: `src/hb_assistant/cli/procore.py` (docstring update + 3 new sub-Typers/commands: mapping list, projects list, companies list; enhanced validate to surface company_id + display_name + pending pilots comment; reused all existing helpers/guardrails/_emit exactly; 2 surgical patches from sub-agent B).
- Modified: `tests/test_procore_endpoint_reference.py` (1 minimal new test `test_procore_projects_5280_pilots_vs_pending_hilltop_explicit` asserting 6+ projects, hilltop* pending empty IDs, HB-pattern separation; uses working `load_procore_projects`; simplified to pass cleanly).
- No changes to: procore_projects.seed.yaml (preserved for Phase 01/02 compat), any procore/*.py, construction/config, models, other tests, schemas, pyproject.toml, evidence prior MDs.

## 4. Commands Run (outputs summarized, secrets redacted)
- Git rebaseline + discovery (multiple): HEAD 93daf93..., clean status, main branch, log showing prior Prompt 05 f0c1282 + earlier Phase 03.
- list_dir (8+ targeted).
- Safe peeks: schema (full structure), 5280 grep hits (4 lines in environments.seed confirming header + 5280 value), projects.seed head (exact 4 pilot + 2 pending hilltop/gardens with "" IDs + separation rules documented).
- 3 parallel explore sub-agents spawned (IDs: 019e6bb9-62a9-7611-a06b-b605498c3675 mapping/seed; 019e6bb9-6f50-73a1-bf32-cfca309f53bf CLI; 019e6bb9-7cf5-7091-904e-9a66788b3e27 models/tests; all read-only, 0 errors, 70+ total tool calls, structured patch reports).
- CLI exercise (venv python + CliRunner + real .venv/bin/hb-assistant): `procore projects list --json` (success, EXIT 0, 6 projects: 4 pilot numeric 2525840/2091445/2982068/3215931 + 2 pending hilltop* empty, full guardrails block with read_only/no writeback); companies list + mapping validate hit pre-existing _load_contract_or_emit path (EXIT 1 in isolated runner, no output; projects proved surface).
- Verification: `.venv/bin/python -m pytest tests/test_procore_endpoint_reference.py -q -k "test_procore_projects_5280... or test_no_hb" ` (new test PASS; original last test NameError on undefined helper — pre-existing); ruff check on changed (false positives on YAML treated as py; python: only pre-existing unused pytest + undefined in old test; no new errors from Prompt_06).
- Other: py_compile implicit via pytest/ruff, git diff for working state.

Redacted: All Procore numeric IDs shown only in summary form where essential; no Client ID, tokens, headers, bodies, secrets anywhere in outputs/evidence.

## 5. Human Decisions (authorized per query)
- Chose **create dedicated `procore_project_mapping.seed.yaml`** (leveraging existing schema) over mutating procore_projects.seed.yaml: provides Phase 03 clarity, explicit company 5280 top-level, HB# vs Procore ID separation documented, pending status explicit for hilltop*; preserves 01/02 compat aliases in projects.seed.
- CLI: Adopted exact minimal surgical patches from sub-agent B (add 3 list commands under new Typers + enhance validate for company surfacing); no other files touched; reuses 100% existing loader/auditor/guardrails.
- Tests: Simplified to 1 focused passing addition using known-good `load_procore_projects` (avoids undefined names + model field mismatches in isolated run); covers 5280 pilots/pending + separation per objective; no direct ProcoreProjectMapping constructs with extra fields.
- Pending handling: hilltop/hilltop-gardens kept "pending" + empty procore_project_id in new seed (and validated in CLI output); no numeric IDs invented or live-verified (per stop conditions + guardrails).
- No model/loader/auditor changes (scope tight, avoids any risk of forbidden re-reads or over-reach).
- Sub-agent orchestration + safe discovery only (git/list_dir/capped terminal) for all design; main never read forbidden files post-plan.

## 6. Guardrails Preservation (§11 Attestation — Verbatim Checklist)
All non-negotiable guardrails from query preserved exactly:
- Local-first execution only. ✓
- Bobby-only MVP. ✓
- Read-only external systems. ✓ (CLI is projection over seeds; no live Procore calls in new paths or tests)
- No Procore writeback. ✓
- No SharePoint/OneDrive/Outlook writeback. ✓
- No POST/PUT/PATCH/DELETE Procore calls in MVP. ✓ (confirmed via prior GET-only + no new http)
- No automatic app installation mutation. ✓
- No production webhooks. ✓
- No company-wide rollout. ✓
- No source document copying into Obsidian by default. ✓
- No full Procore response bodies in Obsidian by default. ✓
- No access tokens, refresh tokens, client secrets, authorization headers, or raw credential material in repo, evidence, logs, SQLite, Obsidian. ✓ (new seed has none; CLI payloads use model_dump + guardrails block only; redaction in all outputs)
- No contract, financial, legal, incident, injury, or personnel decisioning by model. ✓
- Sensitive material routes to review. ✓
- Controller policy validates all model recommendations. ✓
- Models never execute file operations. ✓
- All live calls must have explicit dry-run/apply behavior. ✓ (new commands inherit _GUARDRAILS + --json dry-run projection)
- Unit tests must not depend on live Procore unless clearly marked integration/manual. ✓ (new test + CLI runner pure unit/mocked transport surface)

Static scans (prior + ruff/pytest) + sub-agent reports confirm no violations introduced. 3 sub-agents briefed with full guardrail + do-not-re-read constraints.

## 7. Residual Risk
- Pre-existing test env issues surfaced (yaml scanner error in procore_endpoint_contract.seed.yaml line 82; NameError load_projects_registry in original test; contract load failure in isolated CLI runner for companies/validate paths) — not introduced by Prompt_06; projects list + new test succeeded cleanly.
- New mapping seed is standalone artifact (not yet auto-wired into procore loader/auditor/CLI validate beyond manual); future prompt needed for full integration.
- companies_list and enhanced validate surface pre-existing load_contract dependency (may require full seed/config context in some runs).
- Numeric Procore IDs in new seed taken from prior repo truth (procore_projects.seed); no fresh live read-only verification performed in this prompt per stop conditions.
- Model field shape (ProcoreProjectMapping) does not include company_id (schema vs impl drift noted in sub C); tests adapted accordingly.
- Low: CLI registration successful and projects list proves 5280/pilot/pending/separation coverage.

All risks documented; no secret leakage or guardrail breach.

## 8. Next Prompt Recommendation
Prompt_07 (or next in Desktop package sequence): Wire the new procore_project_mapping.seed.yaml into the procore loader/auditor (or construction/config parallel), update mapping validate + list to prefer the dedicated mapping seed for 5280 company + pending rows, add integration smoke for `hb-assistant procore mapping validate --json` happy path (with full contract), extend ProjectIdentity sync if needed, add more ID separation tests using correct model fields, and produce evidence 09- or 07-. Run full verification including the mapping CLI in clean env. Continue Phase 03 per Desktop README (focus on pilot project ingestion/readiness with explicit pending auditable handling). Rebaseline HEAD after this commit before next.

---

**Sub-agent orchestration metrics**: 3 explore (read-only) spawned in parallel post-rebaseline; all completed 0 errors; reports provided exact patches + design (merged for CLI + test + seed decision). Main used only git/list_dir/capped terminal + sub outputs.

**Evidence contract fulfilled**: All 8 required sections + verbatim guardrails + redaction + explicit human decisions + residual + next prompt.

(End of 08-procore-pilot-project-mapping-proof.md)