# Remediation: Hardened Application Support Permission Handling (Addendum Prompt 02)

Date: 2026-05-25

## Context

Runtime auth and delegated Graph diagnostics previously failed during path initialization when `chmod` on the Application Support root raised `Operation not permitted`.

## Decisions

- `PathPolicy.ensure_dirs()` now supports:
  - `strict_sensitive` to enforce hard-fail behavior only for sensitive auth dir permission requirements.
  - `return_report` to return structured path creation/permission diagnostics.
- Application Support root and other non-sensitive directories use best-effort permission handling and warnings, not hard crashes.
- Auth directory remains the only sensitive directory with `0700` expectation in strict mode.
- Token cache file permission contract remains unchanged (`0600`).

## Runtime Behavior

- Auth/cache initialization no longer hard-fails status-style commands on non-sensitive chmod issues.
- Auth/cache status now carries structured `path_status` with `path_error` and `ensure_report` for diagnostics.
- New `hb-assistant diagnostics paths --json` reports path state and repair recommendations.
- `--repair-dry-run` simulates guidance; `--repair` attempts local non-sudo fixes only.
- CLI never auto-runs `sudo`; manual privileged guidance is advisory text only.

## Validation Outcome

- Command and test evidence recorded under:
  - `docs/evidence/remediation-addendum/prompt-02/`
- No traceback from `Operation not permitted` in required command outputs.
- Required test suite for prompt scope passed.
