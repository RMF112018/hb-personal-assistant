# Package Manifest

## Package

- Name: `graph-procore-dev-ui-connections-implementation-package`
- Date: `2026-06-07`
- Repository: `RMF112018/hb-personal-assistant`
- Expected local path: `/Users/bobbyfetting/hb-personal-assistant`
- Baseline branch/source: `current repo truth at local-agent preflight`
- Baseline HEAD: `capture with git rev-parse HEAD before edits`
- Python package version reported in recent launcher evidence: `1.3.0`
- Frontend package version: `capture from frontend/package.json during P00`

## Source inputs integrated

- User objective prompt for a repo-truth audit and implementation plan covering Graph and Procore Dev UI connection failures.
- Known launcher context: Dev launcher serves Vite at `http://127.0.0.1:5173`, backend is expected on `127.0.0.1:8000`, and Dev source mode uses local/mock data by default.
- Known boundary: Graph and Procore CLI/backend auth/sync surfaces exist from prior terminal validation, but the Dev UI connection flows are not usable.
- Example package structure: `frontend-ui-ux-shell-layout-implementation-package(1).zip`.

## Deliverable intent

This is not a patch set. It is a comprehensive package that directs a local coding agent through repo-truth preflight, implementation, testing, manual validation, and closeout.

## File map

| Path | Purpose |
|---|---|
| `README.md` | Operator overview |
| `01_EXECUTION_GUIDE.md` | Execution sequence and stop conditions |
| `02_REPO_TRUTH_PREFLIGHT.md` | Required repo-truth checks before editing |
| `03_SCOPE_AND_NON_SCOPE.md` | Boundaries and safety constraints |
| `04_TARGET_ARCHITECTURE.md` | Target backend/frontend source connection architecture |
| `05_IMPLEMENTATION_GAP_MAP.md` | Gap-to-prompt map |
| `06_API_CONTRACT_AND_SECURITY_STANDARD.md` | Browser-safe API contract standard |
| `07_COMPONENT_AND_FILE_PLAN.md` | Likely backend/frontend files and component plan |
| `08_VALIDATION_AND_EVIDENCE_PLAN.md` | Automated and manual validation matrix |
| `09_CLOSEOUT_REPORT_TEMPLATE.md` | Final report format |
| `prompts/*.md` | Agent-executable implementation prompts |
| `data/*.json` | Structured gap, API, copy, validation, and guardrail data |
| `reference/*.md` | Audit and design reference notes |

## Execution order

- `P00` — Precheck and branch discipline
- `P01` — Backend environment and aggregate source status contracts
- `P02` — Microsoft Graph safe status/auth bridge
- `P03` — Procore safe status/auth bridge
- `P04` — Source refresh, scheduler, and daily brief status surfaces
- `P05` — Frontend API client and normalized state models
- `P06` — Connection UI cards and workflows
- `P07` — Dev/Production mode, Data Quality, and copy remediation
- `P08` — Tests, security regression coverage, and manual validation
- `P09` — Documentation, closeout, and evidence capture

## No-change confirmation

Generating this package did not modify repo source, frontend source, backend source, migrations, SQLite DBs, auth caches, Graph, Procore, Obsidian, or external systems.
