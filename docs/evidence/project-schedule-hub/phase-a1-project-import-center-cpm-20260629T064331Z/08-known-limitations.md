# Known limitations

- Pre-commit identity preview is best-effort overlap/source-project checks; full identity resolution still runs only on commit.
- Pipeline status is derived from persisted facts; GET status does not recompute CPM or quality.
- Hub readiness may remain `partial` when membership is pending review or baseline is not selected.