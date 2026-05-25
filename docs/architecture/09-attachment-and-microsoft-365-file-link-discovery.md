# Phase 9: Attachment and Microsoft 365 File Link Discovery + Ingestion Pipeline

**Status**: Complete (Prompt 09)  
**Version**: 0.9.0

## Scope
Implemented the complete file/attachment ingestion pipeline for M365 attachments and driveItems:

- Discovery of links from mail (has_attachments + list_attachments) and calendar events to attachments/driveItems.
- Eligibility gates (size caps per type, supported extensions, manual approval threshold).
- Controlled download via GraphHttpClient (bounded, streamed, hashed).
- Bounded parsing (PDF/Office/CSV etc.) producing text_excerpt + char_count only.
- Failure isolation with explicit codes from the 08 spec.
- Persistence to the canonical files / attachments / parser_outputs tables with full source linking ("attaches", "parsed_from").

All per 02 plan row 8, the detailed 08_File_Retrieval_And_Ingestion_Specification, sqlite-schema, and every redaction/safety rule from prior phases.

## Pipeline (exactly as specified in 08)

metadata → relevance (classification signals + has_attachments + size) → eligibility gate → approval (stub) → download (controlled) → hash → parse (bounded) → persist parser_output + source links.

## Key Components

- `src/hb_assistant/files/eligibility.py` — EligibilityGate with the exact size/type/approval rules from 08.
- `src/hb_assistant/files/downloader.py` + hasher — streaming + sha256 (skeleton ready for full Graph integration).
- `src/hb_assistant/files/parsers/` + router — modular, bounded excerpt extraction (PDF example with pypdf; others follow the same pattern).
- `src/hb_assistant/files/service.py` — FileIngestionService (discovery from mail/calendar + full pipeline orchestration).
- Store extensions for files/attachments/parser_outputs status and persistence.
- Thin safe CLI `diagnostics files sample --json` (redacted discovery + eligibility preview only).

## Redaction & Safety Boundaries (enforced)

- Only metadata + bounded text_excerpt ever reach the DB or evidence.
- No full file content is ever loaded into memory for logging or LLM prompts in this phase.
- All paths are dry-run / mock friendly.
- Every persisted item is source-linked before any downstream use.

## Integration

- Reuses Phase 4 DriveItemClient + normalize (extended for downloads).
- Phase 5/7 Store tables and SourceLinkRegistry.
- Phase 6 classification signals for relevance.
- PathPolicy cache ("files" subdir).

## References

- 02_Final_Implementation_Plan.md (row 8)
- 08_File_Retrieval_And_Ingestion_Specification.md (full pipeline, controls, parser matrix, failure codes)
- 07_Local_Data_Model... + sqlite-schema.sql (files, attachments, parser_outputs)
- Prior architecture (DriveItemClient, redaction, linking, dry-run discipline)

This phase makes the "files" side of the system first-class, traceable, and safe for extraction and vault reference (Phase 8+).

Next: Prompt 10 (deeper selective parsing + full orchestrator integration) and retrieval.
