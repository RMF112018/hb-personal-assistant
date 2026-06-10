# Stable output path proof (no auto-open)

- Browser HTML is written to a **stable, non-repo** path under Application Support (`~/Library/Application Support/HB Personal Assistant/html`), with a dated file plus the stable `daily-brief-latest.html` updated only on a fresh success.
- Output dirs inside the repo are refused (fail-closed guard; see `05-failure-status-proof.json`).
- The browser is **never auto-opened**: the installed plist passes `--no-open-browser`, the CLI `--open-browser` flag is reserved (off; emits an `auto_open_not_enabled` warning), and the run summary records `browser_auto_opened: false`.
- The redacted status file records `run_summary.browser_output_path` + `last_successful_path` so the operator always knows where the latest and last-good briefs are.
