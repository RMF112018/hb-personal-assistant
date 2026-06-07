# Phase 10A — Raw Content Enabled Local Intelligence Addendum

Generated: 2026-06-07T19:31:52.391067+00:00

## Purpose

This package is an addendum to Phase 10. It addresses the critical finding from manual local-model testing: metadata-only email/calendar exports are too conservative for useful task, commitment, follow-up, meeting-prep, and project-context extraction.

The addendum instructs the local agent to implement raw-content-enabled local ingestion and endpoint support, starting with email and calendar.

## User decision captured

The user explicitly allows raw content. The implementation should therefore stop treating raw email/calendar content as categorically prohibited and should instead treat it as a **local product capability** with clear configuration, local storage, endpoint, model-context, evidence, and review boundaries.

## Package structure

- `00_PACKAGE_MANIFEST.md` — inventory and execution order.
- `01_OBJECTIVE_AND_SCOPE.md` — controlling scope.
- `02_DECISION_RECORD_RAW_CONTENT.md` — product/security decision record.
- `03_ARCHITECTURE.md` — target raw-content architecture.
- `04_SCHEMA_PLAN.md` — additive schema/storage plan.
- `05_API_ENDPOINT_PLAN.md` — raw-content endpoint behavior.
- `06_EMAIL_PLAN.md` — email raw content ingestion/extraction.
- `07_CALENDAR_PLAN.md` — calendar raw content ingestion/extraction.
- `08_MODEL_CONTEXT_PLAN.md` — local model context using actual content.
- `09_OBSIDIAN_AND_MCP_PLAN.md` — raw-capable downstream exports.
- `10_VALIDATION_AND_ACCEPTANCE.md` — validation gates.
- `prompts/` — ordered local-agent prompts.
- `resources/` — JSON contracts, YAML policy, SQL schema draft, fixtures.
- `runbooks/` — operator runbooks.
- `evidence_templates/` — closeout/evidence templates.

## Core instruction

Implement raw-content-enabled local intelligence. Do not continue testing local models against hashed/metadata-only context when the objective is task/commitment extraction.
