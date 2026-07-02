# Correction package reference

Original evidence:
docs/evidence/project-schedule-hub/schedule-clean-db-full-validation-20260702T124718Z/

Original evidence commit:
2802faa0

Correction scope:
- P1 purge gate (table-level before/after/delta, domain inventory)
- Stage 5 hub/version recapture (canonical routes, status wrappers)
- Stage 6/7 operator API recapture (auth contract, state transition)

Purge DB (local-only): local-sensitive/clean-db/tropical-purge-correction-20260702T133256Z.sqlite
API DB (local-only, with TWNU imports): local-sensitive/clean-db/tropical-full-validation-20260702T124726Z.sqlite
