# 07 — AI Outputs Write-Window Proof

`test_write_window_blocks_repeated_writes` — with `HB_MCP_MAX_AI_OUTPUTS_WRITES_PER_WINDOW=1`
and a 3600s window:
- 1st `ai_outputs_card_upsert` → **allowed** (0 writes in window), receipted to `mutations.jsonl`.
- 2nd → **denied** `write_rate_exceeded` (1 ≥ 1), audited with `rate_limit_result=write_rate_exceeded`.

The counter reads applied `caller_surface="nas_mcp_ai_outputs"` entries in `mutations.jsonl`
within the trailing window (`limits.recent_ai_outputs_write_count`) — reusing the existing
mutation receipts rather than a parallel counter. It is override-aware (`write_count` scope) and
per-client attributed via the authenticated client label where available.

## Fail-closed on unreadable / corrupt receipt state
The limiter never fails open on bad state. `recent_ai_outputs_write_count` distinguishes:
- **missing file** (clean first run) → counts as **0**, write allowed;
- **existing-but-unreadable** file (OSError) or **unresolvable** receipt location → raises
  `WriteWindowStateError`;
- **corrupt/unparseable line** → raises `WriteWindowStateError`. A bad line is not silently
  skipped: it could be an in-window AI-Outputs write we cannot classify, and skipping it would
  undercount and break the window guarantee, so the limiter denies instead.

`check_write_window` maps `WriteWindowStateError` to a denial with reason
`write_rate_state_unavailable`; the broker returns that structured error and audits
`rate_limit_result=write_rate_state_unavailable`. Proven by
`test_write_window_fails_closed_on_unreadable_or_corrupt_state` (corrupt line + a
directory-at-path unreadable case both deny) and `test_write_window_state_error_missing_file_is_zero`
(missing file → 0, not an error).

**Reporter vs limiter split:** the read-only `hb_data_freshness` *reporter* degrades the
`ai_outputs` block to `{status: unknown, note: receipt_state_unavailable}` on the same
condition — a status read must not itself become a denial — while the write *limiter* fails
closed. The two behaviors are intentional and independent.
