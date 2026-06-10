# Deterministic Publishing — Option A (Bobby's choice)

`daily-brief-latest.html` is reserved for FULL synthesis success only. A deterministic fallback
(usefulness passed + synthesis degraded + egress clean) publishes
`daily-brief-latest-deterministic.html`. Always written on a clean run: `daily-brief-<date>.html` +
`daily-brief-latest-attempted.html`. `daily-brief-latest-deterministic.html` updates on BOTH full
success and deterministic fallback (= the latest operator-usable brief). All stable-path writes are
inside the fail-closed `egress_clean` block; egress failure converts the run to `failure` (the
conversion now also catches `deterministic_success_synthesis_degraded`) and publishes neither stable
path. A usefulness-gate failure (`degraded`) publishes neither stable path and preserves
`last-successful.json` (tied to full success only).

## DB-copy proof (Option A)
```
html/
  daily-brief-2026-06-10.html
  daily-brief-latest-attempted.html
  daily-brief-latest-deterministic.html   <- written (PRESENT ✓)
  daily-brief-latest.html                 <- ABSENT ✓ (reserved for full synthesis success)
```
`deterministic_fallback.published = true`, `stable_path = daily-brief-latest-deterministic.html`.
