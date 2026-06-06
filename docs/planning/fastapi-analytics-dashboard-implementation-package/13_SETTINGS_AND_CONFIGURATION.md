# Settings and Configuration

## Settings Placement

Settings is a support-level navigation item, separate from Admin / Data Confidence.

Settings should be role-aware and plain-language. Avoid exposing implementation controls unless they are necessary for setup, admin control, or troubleshooting.

## Construction User Settings

- theme: dark/light/system;
- default landing page: Today, Projects, or My Items;
- pinned/followed projects;
- preferred date range;
- Daily Brief display enabled/disabled;
- Daily Brief output folder and file pattern, if allowed;
- external AI platform selection/instructions for Daily Brief setup;
- notification/attention preferences, if implemented;
- project matching keywords/exclusions;
- Graph reconnect/revoke local credentials;
- Procore reconnect/revoke local credentials.

## Admin Settings

- first sync approval queue;
- per-project sync cadence;
- per-project sync priority;
- initial sync window;
- maximum concurrent syncs;
- source scope management;
- rate-limit/backoff policy;
- project lifecycle state;
- dashboard confidence thresholds;
- retention/storage cleanup;
- auth reconnect/revoke controls;
- Admin / Data Confidence visibility;
- disabled chat stub flag locked disabled.

## Navigation-Related Settings

Allowed default landing pages:

- Today;
- Projects;
- My Items.

Do not offer obsolete default landing choices such as Portfolio, Cost / Change, Documents, Correspondence, Vendors, Billing / Cash, or Closeout as standalone top-level destinations. Those domains are contextual within Today, Projects, and My Items.

## Daily Brief Settings

Daily Brief settings must support:

- show/hide Daily Brief on Today;
- selected external AI platform;
- MCP setup instructions status;
- output folder;
- file naming pattern;
- stale threshold;
- open latest source Markdown;
- test file detection.

The app presents externally generated Markdown as a polished executive brief. It does not generate the Daily Brief through active in-app chat.
