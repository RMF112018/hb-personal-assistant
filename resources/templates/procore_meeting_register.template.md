# Source: HB Construction Intelligence Phase 04 Prompt 10 (resources/templates/). Mirrors the Phase 03 procore_rfi_register template shape; covers meeting + meeting-topic rows persisted by normalize_meeting() / normalize_meeting_topic().

# Meeting Register — {{ project_name }}

## Meetings

| Number | Title | Status | Start | Location | Source |
| --- | --- | --- | --- | --- | --- |
{{ meeting_rows }}

## Topics

| Title | Status | Parent Meeting | Assignee | Due | Safety | Source |
| --- | --- | --- | --- | --- | --- | --- |
{{ topic_rows }}
