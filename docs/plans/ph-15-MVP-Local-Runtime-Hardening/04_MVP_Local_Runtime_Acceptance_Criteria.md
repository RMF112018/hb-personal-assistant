# 04 — MVP Local Runtime Acceptance Criteria

## Functional Acceptance

| ID | Criterion | Required Evidence |
|---|---|---|
| F-01 | Repo is confirmed at expected starting HEAD or deviation documented. | `00-repo-truth.md` |
| F-02 | `actions extract --dry-run --json` succeeds. | JSON output |
| F-03 | `actions list --json` succeeds. | JSON output |
| F-04 | `run morning --dry-run --json` succeeds with full stage model. | JSON output |
| F-05 | Graph consent blocker is classified external and nonfatal. | Morning run output |
| F-06 | Local action extraction produces nonzero seeded results. | Action proof |
| F-07 | Brief generation consumes actions, mentions, files, meetings, retrieval hits. | Brief proof |
| F-08 | Obsidian writer preserves content outside markers. | Obsidian test/evidence |
| F-09 | `written_to_note` provenance is proven on apply path. | DB/source-link proof |
| F-10 | Repeated runs are idempotent. | Idempotency proof |

## Security / Privacy Acceptance

| ID | Criterion | Required Evidence |
|---|---|---|
| S-01 | No Microsoft 365 writeback exists. | Code grep + docs |
| S-02 | No app-only runtime mail/calendar workaround exists. | Code grep |
| S-03 | No full email body persistence. | Code audit + sensitive scan |
| S-04 | No full file content persistence. | Code audit + sensitive scan |
| S-05 | No secrets/tokens/PEMs/cache files committed. | Sensitive scan |
| S-06 | Evidence is redacted and bounded. | Evidence review |

## Quality Acceptance

| ID | Criterion | Required Evidence |
|---|---|---|
| Q-01 | Pytest passes. | Captured output |
| Q-02 | Ruff passes. | Captured output |
| Q-03 | Mypy passes or remaining scope is explicitly documented. | Captured output |
| Q-04 | Ruff/mypy exclusions are reduced for MVP-critical modules where feasible. | `05-validation-scope-hardening.md` |
| Q-05 | Operator runbook exists. | `docs/operations/mvp-local-runtime-operator-guide.md` |
| Q-06 | Final closeout accurately classifies readiness. | `08-final-mvp-candidate-closeout.md` |
