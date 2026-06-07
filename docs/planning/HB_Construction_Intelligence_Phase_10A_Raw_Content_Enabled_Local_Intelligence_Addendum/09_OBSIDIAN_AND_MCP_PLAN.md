# 09 Obsidian and MCP Raw Content Plan

## Objective

Enable downstream raw-content usage where explicitly requested.

## Obsidian

Allow raw-content output to Obsidian only when:

- destination folder is allowlisted;
- user triggers export or config enables it;
- note type is HB-generated or marker-bounded;
- source refs are included.

Examples:

- raw Daily Brief source packet;
- meeting prep packet;
- follow-up queue packet;
- project email context packet.

## MCP

Expose raw content through MCP only when:

- config `mcp.allow_raw_content` is true;
- resource/tool is explicitly raw-capable;
- packet size is bounded;
- source refs are included.

Suggested resources:

- `hb://raw/email/thread/{thread_ref}`
- `hb://raw/calendar/event/{event_id}`
- `hb://packets/raw/daily-brief/{date}`
- `hb://packets/raw/meeting-prep/{event_id}`

## Important

This addendum allows raw content in local MCP context when explicitly enabled. It does not imply external source-system writeback.
