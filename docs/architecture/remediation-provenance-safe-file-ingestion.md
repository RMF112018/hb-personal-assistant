# Remediation: Provenance-Safe File Ingestion (Prompt 08)

## Summary

Prompt 08 separates synthetic/demo ingestion from real ingestion and enforces fail-closed provenance checks on real paths.

## CLI Contract

- `hb-assistant files sample --json`:
  - synthetic records only
  - preview-only behavior
- `hb-assistant files ingest --dry-run --json`:
  - real persisted provenance-backed candidates only
  - no synthetic fallback

## Fail-Closed Rules

Real ingest blocks before download/parse when:

- `source_record_id` missing or non-positive
- Graph metadata required for ingest is incomplete (`id`, `name`, `size`)
- eligibility requires manual approval without explicit approval

Real ingest no longer uses fallback `source_record_id=0` persistence behavior.

## Provenance and Persistence

- Candidate discovery for ingest now comes from persisted `files` rows with valid `source_record_id`.
- Source-link creation remains part of successful real ingest; failures are surfaced as errors and do not report successful ingestion.

## Validation Context

Prompt 08 validation confirms service/test behavior and command contract separation; runtime ingestion readiness still depends on actual persisted file candidates and local config path accessibility.
