# Phase 4 Baseline Summary

## Repo state

| Field | Value |
|-------|-------|
| Worktree | `/Users/bobbyfetting/hb-personal-assistant-worktrees/forecasting-db-audit-20260621` |
| Branch | `feature/forecasting-db-audit-20260621` |
| HEAD (start) | `29f21489e8aa8ae2ccc6e97e52e20aea2540cd59` |
| Phase 3 committed | Yes — PR #71 merged to main (`b954bdac`); worktree includes merge commit |
| Dirty at start | 08c evidence side-effects from tests + untracked evidence tarballs (not Phase 4 scope) |

## Phase 3 evidence reviewed

- `docs/evidence/forecasting-db-audit-20260621/phase3-pr-readiness-report.md`
- `docs/evidence/forecasting-gates-live-copy-20260621T133000Z/` (JSON only; `live-copy.sqlite` gitignored)

## Phase 3 gate summary (live copy, warn mode)

| Gate | ok | warnings |
|------|----|----------|
| double_count_prevention | true | 587 |
| actuals_reconciliation | true | 0 |
| projection_parity | true | 2 |
| cost_type_guard | true | 1 |

Strict mode: fails on double-count (587 promoted warnings) — expected until forecast model applies proven precedence rules.

## Unresolved items entering Phase 4

1. Procore budget formula proof for calculated columns
2. PO projection drift — 5 financial-only keys
3. Per-record projection parity beyond key hashes
4. External eval production workflow beyond allowlist
5. CI/readiness explicit policy for forecast gates

## Phase 4 build posture

Building on committed Phase 3 code with additive Phase 4 changes on a dirty worktree (local test artifacts excluded from commits).