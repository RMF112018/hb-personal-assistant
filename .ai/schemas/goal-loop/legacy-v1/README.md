# Legacy Goal-Loop Schema v1 Compatibility

These schemas are read-only compatibility artifacts. Canonical templates and
new goal records MUST use schema version 2. A version 1 record is admissible only
when it is stored under `.ai/aeos/legacy-v1/` and its path and SHA-256 are listed
in `.ai/aeos/legacy-v1/registry.json`. Empty registry means no legacy record is
currently authenticated.
