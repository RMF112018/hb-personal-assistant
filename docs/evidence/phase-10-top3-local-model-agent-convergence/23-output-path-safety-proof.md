# 23 — Output-Path Safety Proof

## Guards
- `daily_run.run_daily_local_agent` refuses any browser/status/vault output dir inside the repo via
  `_is_in_repo()` → returns `output_path_inside_repo_refused` (failure receipt; writes nothing).
- Default browser output → `PathPolicy.get_html_dir()` (Application Support, NON-repo).
- Status files → `PathPolicy.get_app_support()/daily-run-status` (NON-repo).
- Obsidian note → governed vault dir (NON-repo), requires `--confirm-vault-write`.
- Explicit `--output-path` brief writes (render) must be absolute + outside the repo + marker-bounded.

## Proof
- Test `test_phase_10_daily_run_scheduler_hardening::test_repo_contained_browser_dir_refused_by_daily_run`
  asserts a repo-contained `browser_output_dir` is refused (`ok=False`, `output_path_inside_repo_refused`).
- DB-copy integrated run wrote browser HTML + status only under a `/tmp` disposable dir (non-repo).
- All committed evidence paths are redacted to `~/…` (09/10/20); no absolute home paths remain.
- Browser auto-open is never enabled (`--no-open-browser` emitted; `browser_auto_opened: false`).
