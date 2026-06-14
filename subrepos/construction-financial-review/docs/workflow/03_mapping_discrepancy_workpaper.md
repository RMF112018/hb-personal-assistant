# Stage 3 — Mapping-discrepancy workpaper

**Generator:** `src/construction_financial_review/mapping/generate_mapping_discrepancy_workpaper.py`.

Builds a scope-relationship layer that explains each owner-vs-Procore (`owner_procore_mismatch`) flag
as either a **true progress discrepancy** or a **structural comparison problem** (owner sell value vs
subcontract cost, scope aggregation, placeholder family, deductive credit, etc.). Emits **advisory**
recalibration inputs — it does not modify the analysis package.

`true_progress_discrepancy` requires a comparable basis (percent_complete or remaining_exposure);
owner-vs-Procore dollars are `dollars_with_markup_caution`. Output:
`mapping_discrepancy_workpaper_tropical_<stamp>/`. Conclusion:
`mapping_discrepancy_workpaper_ready_with_unresolved_items`. See
`schemas/mapping_discrepancy_workpaper_schema.md`.
