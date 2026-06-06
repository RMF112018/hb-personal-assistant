# Automated Sync and Freshness

## Goal

The user should open the app and see fresh, prioritized information without maintaining sync jobs manually.

## First Sync

Admin-only. First live sync may be heavy and must protect Procore/Graph rate limits.

## Ongoing Refresh

After first sync, background scheduled/local jobs maintain freshness according to admin cadence and priority.

User-facing status examples:

- Data refreshed 12 minutes ago.
- Next refresh scheduled for 10:00 AM.
- Procore needs reconnect.
- SharePoint folder no longer accessible.
- First sync paused to protect rate limits.

## Admin Controls

- per-project sync cadence;
- live sync priority;
- initial sync window;
- maximum concurrent syncs;
- rate-limit/backoff policy;
- retry policy;
- stale-data thresholds;
- pause/resume/archive project sync.

## Construction User Controls

- request refresh;
- update source connection;
- review stale warnings;
- open admin-required instructions if first sync is blocked.
