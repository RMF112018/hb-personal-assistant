# Known limitations

- `activity_id` remains stripped from PM `top_controls` payloads by design (`_pm_top_control`); activity context is available only in safe route links.
- One skipped test in named-baseline regression set (`..s` in `03-test-results.txt`) is pre-existing; not introduced by Phase 18A.
- Phase 18A does not merge to `origin/main` in this closeout; Phase 19 should branch from merged 18A or await explicit operator authorization.
