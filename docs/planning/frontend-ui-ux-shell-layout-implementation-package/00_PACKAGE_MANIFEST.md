# Package Manifest

## Package

- Name: `frontend-ui-ux-shell-layout-implementation-package`
- Date: `2026-06-07`
- Repository: `RMF112018/hb-personal-assistant`
- Expected local path: `/Users/bobbyfetting/hb-personal-assistant`
- Baseline audit branch/source: `main`
- Baseline audit HEAD/reference: `bc59f1c1631c9525c47477e14c137d85ab6d630d`
- Frontend package version observed in audit: `0.0.0`
- Python package version observed in audit: `1.3.0`

## Source inputs integrated

- Prior audit package: `frontend-ui-ux-shell-layout-audit-package.zip`
- Prior copy package: `HB_Frontend_End_User_Copy_Remediation_Implementation_Package(1).zip`
- Screenshot support: `personal-assistant-screenshots-2026-06-07-0600(1).zip`

## Deliverable intent

This is an implementation package for a local coding agent. It is not a patch set generated in this session. It directs source-code changes to be made locally in the repository after preflight confirmation.

## Package file map

| Path | Purpose |
|---|---|
| `README.md` | Operator overview |
| `01_EXECUTION_GUIDE.md` | How the local code agent should execute the package |
| `02_REPO_TRUTH_PREFLIGHT.md` | Required repo-truth checks before source changes |
| `03_SCOPE_AND_NON_SCOPE.md` | Boundaries and constraints |
| `04_TARGET_ARCHITECTURE.md` | Shell/grid/copy target state |
| `05_IMPLEMENTATION_GAP_MAP.md` | Gap-to-prompt remediation map |
| `06_COPY_REMEDIATION_STANDARD.md` | User-facing copy standard and forbidden patterns |
| `07_COMPONENT_AND_FILE_PLAN.md` | Planned components, hooks, helpers, and likely touched files |
| `08_VALIDATION_AND_EVIDENCE_PLAN.md` | Validation matrix and manual smoke tests |
| `09_CLOSEOUT_REPORT_TEMPLATE.md` | Required final report format |
| `prompts/*.md` | Agent-executable implementation prompts |
| `data/*.json` | Structured gap/prompt/copy/reference data |
| `reference/*.md` | Source audit/copy summaries for traceability |

## Execution order

- `P00` — Preflight and branch discipline
- `P01` — App shell overflow, sidebar footer, and production chrome
- `P02` — Shared layout, card, state, and copy primitives
- `P03` — Today masonry dashboard and copy rewrite
- `P04` — Projects grid and project command-center copy
- `P05` — My Items responsive work-queue grid
- `P06` — Settings guided setup and normalized route consumption
- `P07` — Sidebar Data Quality and Admin/Data Health translation
- `P08` — Visual hierarchy, spacing, typography, responsiveness, and accessibility hardening
- `P09` — Copy regression harness, docs, and closeout evidence

## No-change confirmation for package generation

Generating this package did not modify repository source code, frontend code, backend code, migrations, operator DB, auth cache, Graph, Procore, Obsidian, or external systems.
