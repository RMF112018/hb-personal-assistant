# 05 — Project Resolution & Review

Reuses `project_aliases.resolve_project` / `candidate_tokens`. Explicit row project_key preferred;
project-like-but-unresolved -> review_required with project_key = None; otherwise not_project_related.
**No invented keys.**

Real-data (owner-configured): resolved=2,
review_required=2,
not_project_related=0,
project_key_coverage=0.5. Invented keys found: **0**.

Low coverage is reported honestly and accompanied by review_required items; the usefulness gate fails
low coverage only when nothing is flagged for review.
