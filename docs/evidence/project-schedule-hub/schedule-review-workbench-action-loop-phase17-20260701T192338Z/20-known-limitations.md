# Known limitations — Phase 17

- Legacy `open`/`watching`/`reviewed`/`dismissed` accepted as API aliases but stored canonically after V98 migration.
- `watching` collapses to `needs_review` in canonical storage (no separate watching bucket).
- `blocked_by_identity` / `blocked_by_trust` are system-assigned only; not operator dropdown choices.
- Browser evidence screenshots not captured in automated closeout (require local app + fixture DB).
- V98 migration is forward-only; rollback requires DB restore.
- Bulk POST sync remains for automation; primary operator path is selective promote + manual sync button.
