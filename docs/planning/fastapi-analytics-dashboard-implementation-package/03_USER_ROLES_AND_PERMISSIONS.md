# User Roles and Permissions

## Construction Management User

Can:

- authenticate Graph and Procore locally;
- view Today, Portfolio, Projects, Meetings, Action Items, and operational dashboards;
- add/manage data connection URLs;
- select OneDrive scope;
- manage project matching keywords and exclusions;
- request project refresh;
- mark local review items reviewed;
- open source-linked records;
- configure Daily Brief display and output folder, subject to setup requirements;
- manage personal preferences such as theme and pinned projects.

Cannot:

- trigger or schedule the first live sync for a project;
- change rate-limit budgets;
- modify global sync priorities;
- enable source-system writeback;
- see tokens or raw sensitive content;
- enable active in-app chat;
- alter hard safety guardrails.

## Admin User

Can:

- all Construction Management User actions;
- approve/schedule/trigger first project live sync;
- set per-project sync cadence and priority;
- set initial sync windows;
- pause/resume/archive sync;
- manage rate-limit/backoff policy;
- manage retention/storage cleanup;
- manage source scopes and exclusions;
- view Admin / Data Confidence dashboards;
- inspect job/evidence/guardrail status;
- reconnect/revoke local credentials.

## Permission Rule

Only Admin can trigger or schedule the first live sync for a project. Construction users may prepare the connection and request sync, but admin approval protects rate limits and heavy historical ingestion.
