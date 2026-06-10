# 05 — Backfill, Reprocessing, and Coverage

## Objective

Implement safe local backfill and reprocessing commands so existing Procore data can populate the new raw/structured analytics foundation without unnecessary live Procore calls.

## Required commands

Add CLI/status commands, names adjusted to repo conventions, for inspecting endpoint structured coverage, backfilling raw landing from current live records only where safe and documented, reprocessing raw landing into structured family tables, regenerating projections from structured family tables, regenerating ranked Procore signals from structured family tables, and reporting gaps by endpoint/family/project.

Backfill from `canonical_json_redacted` is allowed only as a partial historical bootstrap and must be labeled as `source_quality=redacted_legacy_projection`. It must not be misrepresented as complete raw endpoint payload capture.

New live captures after this package should populate true raw landing and structured family tables.

## Required modes

Every command must support `--dry-run` default, explicit `--apply`, project filter, endpoint/family filter, row caps, JSON output, Markdown output, and no-live-Procore-call mode.

## Required coverage gates

Coverage report must fail or degrade honestly when raw landing is missing, structured table is missing, endpoint identity is unresolved, current rows cannot be distinguished from historical rows, source refs are missing, projected rows exceed raw rows without explanation, or raw landing only came from redacted legacy projection.

## Required tests

No live Procore calls during reprocessing, backfill labels source quality honestly, coverage report is deterministic, dry-run writes nothing, apply writes bounded rows only, and production DB unchanged during validation.

## Evidence

Write evidence under `docs/evidence/procore_endpoint_structured_analytics_foundation/05-backfill-reprocessing-and-coverage/`.
