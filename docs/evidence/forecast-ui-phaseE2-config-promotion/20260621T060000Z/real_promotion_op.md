# Real live promotion — PENDING (separate authorized op)

The real promotion against the actual live config DB is intentionally NOT run in CI. It is a
human-gated operation. To perform it:

1. Enable the opt-in: set HB_FORECAST_PROMOTION_ENABLED=1 (env or the runtime settings flag).
2. In the UI, open a parity-passed proposal and click "Promote to live" (explicit confirm), OR run
   the CLI: `construction_financial_review.cli forecast-config-registry-promote --project tropical
   --edited-config-root <proposal>/edited_config --work-root <isolated> --context-stamp <stamp>
   --snapshot-name <name> --snapshot-reason <reason> --allow-live-db-write --expect-item-count <N>`.
3. The workflow backs up the live DB first (fail-closed on nonzero WAL), writes one additive snapshot
   in a single transaction, and certifies it. Record the redacted report + backup sha here when run.

Load-bearing safeties: the default-OFF opt-in, the per-request confirm, and the byte backup.
