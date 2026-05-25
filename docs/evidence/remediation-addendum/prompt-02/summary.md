# Addendum Prompt 02 Summary

## Result

`COMPLETE` for prompt-02 implementation scope.

## Changes implemented

- Refactored `PathPolicy.ensure_dirs()` with richer policy controls:
  - `strict_sensitive` and `return_report` support.
  - structured per-path report (`path`, `kind`, `exists`, `writable`, `mode`, `owner`, `chmod_attempted`, `chmod_ok`, `error`).
  - non-sensitive directory permission issues are warnings, not hard crashes.
- Hardened `TokenCacheManager` initialization:
  - captures path ensure report and `path_error` status for diagnostics/auth payloads.
  - hard-fails only on write operations when secure cache path is unavailable.
- Added `hb-assistant diagnostics paths --json` plus `--repair-dry-run` and `--repair` options.
  - emits path status, warnings/failures, local repair attempts, and manual repair recommendations.
  - does not execute `sudo`.
- Added/updated targeted tests in `test_config`, `test_auth`, and `test_cli_canonical`.
- Added architecture note:
  - `docs/architecture/remediation-hardened-app-support-permissions.md`

## Validation status

- `hb-assistant diagnostics paths --json` passed.
- `hb-assistant auth status --json` returned valid JSON (exit 1 due network name-resolution; no permission traceback).
- `hb-assistant diagnostics graph --safe --json` returned valid JSON (exit 1 due network name-resolution; no permission traceback).
- `python -m pytest tests/test_auth.py tests/test_config.py tests/test_cli_canonical.py` passed (`36 passed`).
