# Bug / gap log — CPM formula trace hardening

| ID | Severity | Item | Disposition |
|----|----------|------|-------------|
| G1 | known limitation | Longest-path independent shadow replay not implemented | Documented as `not_evaluated`; diff status `pass_with_exclusions` |
| G2 | fixed | Relationship ref key mismatch (`relationship_row_id` vs `A1000->A1010 (FS)`) broke triple diff | Normalized via `_relationship_ref()` + shadow ID preference |
| G3 | fixed | `LagNormalizationResult.normalized_days` attribute name | Corrected in shadow recompute path |
| G4 | open | Calendar-aware duration/lag normalization in shadow may diverge from engine on complex calendars | Accept for phase-0; fixture uses standard 8h calendar |
| G5 | open | Backward relationship persisted fields not triple-diffed in relationship trace | Forward candidate ES triple-diff covered; backward/free-float shadow values exported but not fully triple-gated |

No blocking defects for phase-0 fixture validation.
