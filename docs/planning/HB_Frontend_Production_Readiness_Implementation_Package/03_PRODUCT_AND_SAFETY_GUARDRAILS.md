# 03 Product and Safety Guardrails

## Product Direction

The frontend is a local-first construction time-management and data-intelligence command center for a general contractor. It should surface what matters, reduce context switching, and support preparation/action without requiring the user to understand backend mechanics.

## Top-Level Navigation

Only these top-level sections should be exposed:

```text
Today
Projects
My Items
Admin / Data Confidence
Settings
```

All domain-specific experiences must be contextual:

- Meetings: Today, Projects, My Items.
- Field Operations: Projects.
- Startup / Closeout / Daily Logs / Observations / Punch / Schedule: Projects > Field Operations or Projects > Cost & Time.
- Documents / Correspondence / OneDrive / SharePoint: Today, Projects, My Items, or Settings connection setup.
- Billing / Cash / Cost / Change / Forecast support: Projects > Cost & Time or Today summary signals.

## Chat Boundary

Chat is future/stub-only. There must be no active or accessible in-app chat interface. Do not add a chat page, composer, chat drawer, streaming endpoint, conversation API, or local prompt surface.

## External Systems Boundary

- Dashboard/read-model routes must not call live external APIs.
- Setup preview/save flows must not start live syncs.
- Source-system writeback is prohibited.
- Admin first live sync approval/scheduling must remain admin-only.

## Serialization Boundary

Do not serialize or persist the following in UI responses, frontend state snapshots, tests, evidence, logs, or diagnostics:

- raw email bodies;
- raw calendar body content;
- meeting join URLs;
- raw document text;
- raw prompts or model responses;
- tokens, refresh tokens, secrets, signed URLs, download URLs;
- PEM material, certificates, private keys;
- auth cache contents.

## Daily Brief Boundary

The Daily Brief is generated outside the app by an external agent as Markdown. The app may detect, parse, present, and preserve the Markdown. It must not silently alter the original file, perform external-agent orchestration inside the UI, or convert Daily Brief setup into in-app chat.
