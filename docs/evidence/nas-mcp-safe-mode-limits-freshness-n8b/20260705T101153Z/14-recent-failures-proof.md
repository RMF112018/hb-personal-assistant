# 14 — Recent Failures Proof

`hb_recent_failures` scans a fixed set of run tables (`assistant_runs`,
`second_brain_run_registry`, `*_crawl_runs`, `procore_live_sync_runs`) for
`status IN ('error','failed')`, returning per-subsystem `failed_count` + a bounded list of
`{at, error_class}` where `error_class` is passed through `redact_text`. No raw payloads, no
rel_paths, no decrypted content.

`test_recent_failures_redacted_no_payload` (seeded `assistant_runs` with one error row):
`subsystems.assistant_runs.failed_count == 1`. Absent tables → `{status: not_configured}`.
Read-only, available in safe mode, requires origin auth. The list length is capped
(default 10, hard max 50).
