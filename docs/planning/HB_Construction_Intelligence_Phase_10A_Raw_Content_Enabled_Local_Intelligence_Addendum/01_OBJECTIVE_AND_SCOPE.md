# 01 Objective and Scope


## Raw-content policy for this addendum

This addendum intentionally changes the working assumption from “metadata-only” to **raw-content-enabled local intelligence**.

Raw content is allowed for local ingestion, local persistence, local API endpoints, local model context, local dashboard review, Obsidian output when explicitly requested, and MCP packets when explicitly requested.

Raw content includes, at minimum:

- email subject;
- email body preview;
- email plain-text body;
- email HTML body or sanitized/renderable HTML body;
- email sender/recipient display names and addresses;
- attachment names and metadata;
- calendar subject;
- calendar body/description;
- calendar location;
- attendee/organizer names and emails;
- online meeting provider and join URL;
- calendar recurrence/series metadata;
- file/document names and text once file endpoints are implemented.

Raw content remains local-first. This package does not approve external writeback, automatic email sending, automatic calendar mutation, Procore writeback, or cloud LLM submission. External exposure is a separate future decision.


## Objective

Implement Phase 10A as an aside/addendum to Phase 10:

1. Allow raw content across local endpoints.
2. Start with email and calendar raw content.
3. Persist raw content locally in the Dev/Production SQLite DB or associated local content store according to explicit config.
4. Expose raw content through backend endpoints when raw-content mode is enabled.
5. Feed bounded raw content to local models for action-intelligence extraction.
6. Generate task, commitment, follow-up, meeting-prep, and relationship candidates from actual content.
7. Preserve source references, timestamps, and review status.

## In scope now

- Email subject/body/preview/sender/recipient raw content.
- Calendar subject/body/location/attendees/organizer/join URL raw content.
- Raw content schema additions.
- Raw content config policy.
- Raw content backend endpoint support.
- Raw content model-context packet builder.
- Frontend raw-content review surfaces.
- Dev and Production path isolation.
- Local model tests using raw content.
- Evidence proving raw content is intentionally enabled.

## In scope by architecture, later implementation waves

- Files/documents raw text.
- Procore raw payloads or selected raw field preservation.
- Obsidian raw-content exports.
- MCP raw-content packets.

## Out of scope

- External writeback.
- Automatic email send.
- Calendar mutation.
- Procore mutation.
- Cloud LLM submission.
- Publishing raw content outside the local machine.
