# Recompute Readiness

No safe selected-baseline recompute queue or trigger was wired in Phase 8A.

Derived readiness rules:

- A selected baseline must be a committed schedule version for the same project.
- Current and selected baseline versions must differ.
- Selected baseline data date must not be later than current data date.
- If identity evidence exists for both versions, identity keys must match.
- Compression readiness requires matched unfinished activities and usable duration_remaining or duration_original fields.

When matching or duration facts are missing, the API returns recompute_required true with structured blockers instead of fabricating selected-baseline comparison values.
