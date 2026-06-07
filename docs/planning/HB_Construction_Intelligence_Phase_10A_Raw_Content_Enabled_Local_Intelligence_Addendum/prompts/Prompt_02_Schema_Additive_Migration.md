# Prompt 02 — Raw Content Schema Migration

## Objective

Implement additive schema for raw email/calendar storage.

## Tasks

1. Add migration for raw-content tables.
2. Add indexes.
3. Add row-count/status helpers.
4. Add tests for migration idempotency.
5. Do not delete existing metadata-only tables.

## Acceptance

- Migration applies cleanly.
- Existing tests pass.
- Raw tables exist.
