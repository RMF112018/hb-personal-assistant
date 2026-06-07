# 08 Local Model Context Plan

## Objective

Stop testing models against hashed metadata. Build raw-content context packets.

## Packet types

- `email_thread_action_packet`
- `calendar_meeting_prep_packet`
- `daily_brief_raw_packet`
- `project_raw_context_packet`

## Example email packet

```json
{
  "packet_type": "email_thread_action_packet",
  "thread_ref": "...",
  "project_key": "...",
  "messages": [
    {
      "direction": "inbound",
      "from_name": "...",
      "from_address": "...",
      "received_at_utc": "...",
      "subject": "...",
      "body_text": "...",
      "attachments": []
    }
  ]
}
```

## Required model output

Strict candidate schema with no generic placeholders.

## Anti-junk rule

Reject candidates titled or classified as:

- data_cleaning;
- data_analysis;
- data_enhancement;
- generic review data;
- anything not grounded in actual email/calendar content.

## Retry flow

1. Generate with schema.
2. Validate schema.
3. Validate business contract.
4. If invalid, run one repair attempt.
5. If still invalid, mark failed and persist receipt.
