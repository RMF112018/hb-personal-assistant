# Known limitations — Phase 13B

| ID | Issue | Class | PR impact | Production rollout |
|----|-------|-------|-----------|-------------------|
| L1 | Named export `current_contract_baseline` / `secondary_progress_update_baseline` returns **422** `narrative_qa_failed` | **P1** | Does not block core comparison-accuracy PR | Blocks full export sign-off |
| L2 | Export `previous_progress_update_baseline` returns 200 but excerpt lacks explicit `comparison_basis` string | **P2** | Document only | Verify memo body in UI before rollout |
| L3 | Legacy `comparison_basis=baseline` unavailable on Tropical (`baseline_unavailable`) | **Real-DB limitation** | Expected — named slots are primary path | N/A for Tropical |
| L4 | Driver Detail API/UI lacks disposition fields (`review_status`, etc.) | **P2 / follow-up** | Not a blocker when Controls + Workbench prove comparison | Follow-up slice |
| L5 | Controls `top_controls` expose `review_item_id` but often `review_status: null` | **Evidence-only** | Disposition proof via Workbench `psnbri-*` rows | Acceptable |
| L6 | Frontend vitest: `ProjectSchedulePage` export spy expects no `comparisonBasis` (13A added param) | **Frontend-only** | Test fix follow-up | Non-blocking |
| L7 | Tropical API requests slow on operator laptop (15–180s) | **Evidence-only** | Observability | N/A |
| L8 | Browser shot `08-driver-detail-disposition` — disposition UI absent | **P2 / follow-up** | Manifest `loaded: false` acceptable | Follow-up |

## Export named-awareness (per 13B amendment)

| Basis | HTTP | Named-aware? | Notes |
|-------|------|--------------|-------|
| `prior_update` | 200 | yes | `includes_comparison_basis: true` in excerpt |
| `baseline` | 200 | no | Legacy path; not available in controls anyway |
| `current_contract_baseline` | 422 | fails safe | Explicit `narrative_qa_failed`; **no** silent prior-update fallback |
| `previous_progress_update_baseline` | 200 | partial | 200 response; basis string not confirmed in excerpt |
| `secondary_progress_update_baseline` | 422 | fails safe | Explicit `narrative_qa_failed` |

**Do not describe export as fully named-aware** until L1 is resolved or product accepts 422 as the safe degraded behavior for memo export.
