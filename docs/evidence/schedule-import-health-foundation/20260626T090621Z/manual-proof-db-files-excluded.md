# Manual Proof Database Files Excluded

SQLite proof databases, WAL files, and SHM files were intentionally excluded from Git history.

Reason:
- Local proof DBs are generated artifacts.
- At least one proof DB exceeded GitHub's 100 MB file limit.
- The committed evidence retains reproducible JSON outputs, preview/commit/health-data payloads, DB count summaries, and README summaries.

Retained evidence:
- manual-package-proof README and JSON artifacts
- manual-zip-package-proof README and JSON artifacts
- DB count JSON files
- schema/version/capability summaries
