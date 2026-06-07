# 07 Calendar Raw Content Plan

## Objective

Enable raw calendar content for meeting prep and follow-up intelligence.

## Ingestion

Update calendar event indexing to persist:

- subject;
- body/description;
- body preview if available;
- location text;
- organizer name/email;
- attendee names/emails/status;
- online meeting provider;
- join URL;
- recurrence/series metadata.

## Storage

Persist raw content in `calendar_event_raw_content`.

## Model use cases

- meeting prep checklist;
- agenda extraction;
- related email/thread hints;
- follow-up actions from past meetings;
- project relationship inference;
- attendee/company relationship extraction.

## UI use cases

- show calendar body and attendees in Meeting Prep;
- link raw event detail to action candidates;
- support “prepare packet” from selected meeting.
