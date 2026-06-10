# 01 DB Audit And Schema Baseline

Safe copied-DB audit used SQLite `.backup` at
`/tmp/hb-procore-structured-analytics-foundation-audit-20260610-054842/prod-backup-20260610-054842.sqlite`.

- Production DB size: `242M`.
- Production DB hash before validation: `f93b78081dfbbd7d40ebbfc9254227eab7d306bb08d73e8b92d76e7b33ae4759`.
- Backup hash: `45fb3ae27226b2041685dccb5529640ec2130cc2306a656e4dfee4564e4fe5b6`.
- Backup integrity check: `ok`.
- Backup quick check: `ok`.
- Copied DB source schema before migration: `45`.
- Production DB hash after validation: `f93b78081dfbbd7d40ebbfc9254227eab7d306bb08d73e8b92d76e7b33ae4759`.

Process preflight saw one existing pytest process; no scheduler, refresh, uvicorn, or live Procore
process was killed or modified.
