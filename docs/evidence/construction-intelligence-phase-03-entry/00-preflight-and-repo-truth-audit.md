# Phase 03 Entry — Prompt 00: Preflight and Repo-Truth Audit

- Date: 2026-05-27
- Prompt source: `/Users/bobbyfetting/Downloads/HB_Construction_Intelligence_Phase_03_Entry_Package/prompts/Prompt_00_…` (per package README at the package root)
- Evidence path: `docs/evidence/construction-intelligence-phase-03-entry/00-preflight-and-repo-truth-audit.md`
- Scope: read-only repo-truth audit. **Procore OAuth proof is excluded from this entry gate.** No source-system mutations.

## 1. Repo HEAD, branch, working tree

```text
$ git status --short
(empty — clean working tree)

$ git branch --show-current
main

$ git rev-parse HEAD
a4d80c357f100540e47c4919f9ddad8c5362044d
```

Working tree is clean. HEAD == `origin/main` == `origin/HEAD` == `a4d80c3` (see decorated log below). No unpushed commits at the time of capture.

## 2. Recent commit log (last 30, decorated)

```text
$ git log --oneline --decorate -30
a4d80c3 (HEAD -> main, origin/main, origin/HEAD) docs(evidence): add construction-intelligence-phase-03/00-repo-truth-and-phase-02-rebaseline (HB Construction Intelligence Phase 03 Prep v1.3.0)
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
8dd32e1 feat(construction-agent): add procore endpoint audit foundation
d55ba07 feat(construction-agent): add cli surface
aea535b feat(construction-agent): add ollama structured classification
7d0908c feat(construction-agent): add review queue policy
057122f feat(construction-agent): add obsidian construction vault writer
2aa69e6 feat(construction-agent): add source manifests and receipts
9ff7ed1 feat(construction-agent): add graph delta crawler
f8310b3 feat(construction-agent): add source registry config model
439c010 chore(construction-agent): add phase 01 governance preflight evidence
```

Phase boundaries visible:
- Phase 01 scaffold close: `34728c1`.
- Phase 02 chain: `cd9f014` → `a45ddd2` (18 commits).
- Phase 03 Prep v1.3.0 (separate package; introduced `docs/evidence/construction-intelligence-phase-03/`): `a4d80c3`.

## 3. Phase 02 evidence file inventory

```text
$ find docs/evidence/construction-intelligence-phase-02 -maxdepth 2 -type f | sort
docs/evidence/construction-intelligence-phase-02/00-phase-02-preflight-and-phase-01-acceptance-rebaseline.md
docs/evidence/construction-intelligence-phase-02/01-source-registry-reality-alignment.md
docs/evidence/construction-intelligence-phase-02/02-canonical-sqlite-schema-and-adapters.txt
docs/evidence/construction-intelligence-phase-02/03-graph-folder-scoped-resolution-proof.json
docs/evidence/construction-intelligence-phase-02/04-tropical-baseline-delta-and-receipt-proof.json
docs/evidence/construction-intelligence-phase-02/05-hilltop-projecthome-discovery.md
docs/evidence/construction-intelligence-phase-02/06-onedrive-inventory-first-baseline.md
docs/evidence/construction-intelligence-phase-02/07-procore-mapping-correction-and-audit-readiness.md
docs/evidence/construction-intelligence-phase-02/08-obsidian-output-quality-proof.md
docs/evidence/construction-intelligence-phase-02/09-review-policy-and-ollama-live-readiness.md
docs/evidence/construction-intelligence-phase-02/10-email-intelligence-deferred-foundation.md
docs/evidence/construction-intelligence-phase-02/11-documentation-evidence-truthfulness-closeout.md
docs/evidence/construction-intelligence-phase-02/12-final-validation-output.txt
docs/evidence/construction-intelligence-phase-02/session-handoff.md
```

14 files present: prompts 00 → 12 (13 files) plus `session-handoff.md`. Required Phase 02 evidence is complete.

## 4. Validation outputs

### 4.1 `python -m pytest tests/test_construction_*.py tests/test_procore_*.py tests/test_mutation_lockout.py`

```text
........................................................................ [ 17%]
........................................................................ [ 34%]
........................................................................ [ 52%]
........................................................................ [ 69%]
........................................................................ [ 87%]
.....................................................                    [100%]
413 passed in 5.77s
```

Matches Phase 02 closeout baseline (413 passed). No regressions.

### 4.2 `ruff check src/hb_assistant/construction/ src/hb_assistant/procore/ src/hb_assistant/cli/construction.py src/hb_assistant/cli/procore.py`

```text
All checks passed!
```

### 4.3 `hb-assistant construction-agent validate --json`  (exit 0)

```text
schema           ok=True  schema_version=5
source_registry  ok=True  6 projects, 14 sources
review_rules     ok=True  version=1; 16 rules; threshold=0.7
model_routing    ok=True  version=1; default_model=llama3.2:1b; tasks=['classification', 'review_reason']
summary          total=4, passed=4, failed=0, ok=True
guardrails       external_systems=read_only, writeback=none, metadata_only=true,
                 command_role=read_only_dashboard
```

### 4.4 `hb-assistant construction-agent sources validate --json`  (exit 0)

```text
implemented=True  phase=1  step=2-source-registry
summary           project_count=6, source_count=14, resolved_count=0,
                  pending_count=9, deprecated_count=0, ok=True, blocking=False
warnings          ["9 sources pending live resolution"]
guardrails        all_read_only=True, no_writeback_paths=True,
                  no_live_external_calls=True
note              "Read-only validation. No SharePoint/OneDrive/Graph calls
                  were made."

source_keys (14)  tropical-sharepoint, hilltop-sharepoint, bobby-onedrive,
                  sp_2023projects_23_435_01_tropical_sl,
                  sp_2025projects_25_264_01_atlantic_fields_club_core,
                  sp_2022projects_22_112_01_pga_the_modern_garage,
                  sp_2024projects_24_606_01_alton_hilltop_pbg,
                  sp_2025projects_25_244_01_the_wellington,
                  sp_2026projects_26_727_01_wellington_marketplace_condo_hotel,
                  sp_2026projects_26_898_01_wellington_townhomes,
                  sp_hilltop_gardens_projecthome,
                  od_business_bobby_hedrickbrothers,
                  od_personal_bobby,
                  od_shared_libraries_cloudtemp
```

### 4.5 `hb-assistant construction-agent index status --json`  (exit 0)

```text
schema_version=5
summary           project_count=6, source_count=14, sources_in_view=14
review_queue      open=0, resolved=0, deferred=0
model_decisions   accepted=1, review=2
policies.review_rules    version=1, rule_count=16,
                         low_confidence_threshold=0.7
policies.model_routing   version=1, default_model=llama3.2:1b,
                         low_confidence_threshold=0.7,
                         tasks=['classification', 'review_reason']
guardrails        external_systems=read_only, writeback=none,
                  metadata_only=true, command_role=read_only_dashboard
```

### 4.6 `hb-assistant construction-agent ollama status --json`  (exit 0)

```text
endpoint_url              http://localhost:11434
endpoint_source           default
daemon_reachable          False
expected_models           ['llama3.2:1b']
present_models            []
missing_models            ['llama3.2:1b']
suggested_pull_commands   ['ollama pull llama3.2:1b']
status                    daemon_unreachable
ok                        False
error_redacted            ollama_request_failed
guardrails                external_systems=read_only, writeback=none,
                          live_inference=false, endpoint_path=/api/tags
```

Exit 0 confirms the offline-CI-safe contract added in Phase 02 Prompt 09 still holds.

## 5. Failure classification

Per the package acceptance criteria, every non-pass is classified:

| Item | Observation | Classification |
|------|-------------|----------------|
| `procore mapping validate` | Not invoked by this prompt — Prompt 00 deliberately omits it. | n/a (Procore OAuth proof is excluded from this entry gate). |
| 4 pre-existing `tests/test_obsidian_writer.py` failures | Excluded by selector (`test_construction_*`, `test_procore_*`, `test_mutation_lockout`). | **pre-existing known limitation** (predates Phase 02; carried in Phase 02 §5 handoff). |
| `ollama status` → `daemon_unreachable`, `ok=False` | Local daemon not running; `llama3.2:1b` not pulled. Exit 0 by design. | **environment-only blocker** (offline-CI-safe by construction). |
| 9 sources `pending*` in `sources validate` | Live Graph token required to flip to `resolved`. | **environment-only blocker** (no delegated token in MSAL cache). |
| `sources validate` itself | `ok=True`, `blocking=False`. | pass. |
| Everything else | All exit 0; all `ok=True`. | pass. |

No **new blocker** observed.

## 6. Known unresolved live validations (carry-forward)

These are out of scope for the entry gate and are tracked for Phase 03 work:

- Live Microsoft Graph delta crawl — no delegated token; `graph sources resolve` would return `auth_required`.
- Live Procore OAuth — intentionally deferred per the package's scope boundary.
- Live Ollama daemon round-trip — `llama3.2:1b` not pulled; daemon not running.
- Live mailbox metadata fetch — deferred per Phase 02 Prompt 10 email-intelligence policy.
- 9 source-registry entries marked `pending` / `pending_drive_resolution` / `pending_graph_resolution` / `pending_source_resolution`.
- 2 Procore mappings marked `pending` (`hilltop`, `hilltop-gardens`).

## 7. Procore OAuth exclusion (verbatim per prompt)

> Procore OAuth proof is excluded from this entry gate. Procore OAuth and live Procore API proof will be addressed inside Phase 03 as a later dedicated workstream.

`procore mapping validate` and live Procore endpoints were intentionally not invoked in this preflight. The Phase 02 Prompt 07 mapping correction (`23-435-01` → `2525840`, seed 2 → 6, HB-number-shape validator) remains the active baseline.

## 8. Acceptance attestation

- [x] Evidence directory exists: `docs/evidence/construction-intelligence-phase-03-entry/` (created by this prompt).
- [x] Preflight evidence file created: this file.
- [x] Tests, ruff, and validate results recorded verbatim.
- [x] All non-passes classified (none are `new blocker`).
- [x] No source-system writeback attempted. All commands declare `writeback=none`, `external_systems=read_only`, `live_calls_disabled=true` where applicable.
- [x] Working tree had no unrelated user changes (`git status --short` empty; HEAD == `origin/main`).
- [x] Required Phase 02 evidence is present (14 files under `docs/evidence/construction-intelligence-phase-02/`).
- [x] No stop condition tripped.

Phase 03 entry preflight is **PASS**. Ready to proceed to Prompt 01 of the Phase 03 Entry Package.
