# 14 Claude MCP Context Packet Plan

## Purpose

Prepare compact, source-linked packets that make Claude more useful through MCP without exposing raw unrestricted data or writeback tools.

## Packet types

- `daily_brief`
- `meeting_prep`
- `project_review`
- `follow_up_queue`
- `weekly_action_review`
- `obsidian_update_plan`

## MCP resources

- `hb://daily-brief/latest`
- `hb://daily-brief/{date}`
- `hb://projects/{project_key}/summary`
- `hb://projects/{project_key}/signals`
- `hb://tasks/open`
- `hb://tasks/waiting-on-me`
- `hb://tasks/waiting-on-others`
- `hb://meetings/upcoming`
- `hb://meeting/{event_id}/prep`
- `hb://source-ref/{source_ref_hash}`
- `hb://obsidian/daily-brief/latest`
- `hb://claude-packets/{packet_id}`

## MCP tools

Read-only/local-only:

- `build_claude_context_packet`
- `get_project_context`
- `get_meeting_prep_packet`
- `get_follow_up_queue`
- `search_source_refs`
- `list_daily_brief_candidates`
- `export_packet_to_obsidian`

No arbitrary SQL or writeback tools.
