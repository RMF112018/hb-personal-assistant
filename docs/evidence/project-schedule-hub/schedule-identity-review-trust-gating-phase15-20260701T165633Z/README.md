# Phase 15 — Schedule Identity Review + Trust Gating UX

**Branch:** `feature/schedule-identity-review-trust-gating-phase15-20260701T165632Z`  
**Base:** `258e043b` (Phase 14 on main)  
**Verdict:** Ready for operator review (no push/PR without approval)

## Delivered

- `project_schedule_identity_trust_service.py` — PM-safe identity trust read model
- `identity_gate` integrated into Phase 14 `analytics_trust` ledger (blocked overrides CPM-ready)
- Import preview/status identity trust + redacted `trust_preview`
- Hub `identity_review` + `analytics_trust.identity_trust` enrichment
- Controls identity trust section
- Export memo identity trust lines
- `TrustBanner.tsx` component (identity + analytics gating)
- Import preview identity message panel

## Validation

```bash
pytest tests/test_project_schedule_identity_trust.py tests/test_project_schedule_analytics_trust.py \
  tests/test_project_schedule_import_pipeline.py tests/test_project_schedule_hub_api.py \
  tests/test_project_schedule_named_baseline_workbench.py tests/test_schedule_trust_resolver.py -q

cd frontend && npm test -- --run ProjectSchedulePage.test.tsx
```

## Deferred (Phase 15B)

- Browser screenshot evidence (14–18) — requires running app against tropical DB
- JSON fixture captures (05–13) — capture during operator smoke if needed
