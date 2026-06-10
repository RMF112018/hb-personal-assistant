# Daily-brief consumption proof (no duplication, degraded-honest)

The daily brief consumes Procore via two complementary, non-overlapping surfaces:

| Surface | Source | Role |
|---|---|---|
| `build_procore_action_digest` (existing) | `procore_action_signals` | the brief's Procore action items (dry-run; idempotent persist to `daily_brief_action_candidates`) |
| `procore live monitor` (this candidate) | `procore_live_*` freshness + endpoint registry | the health/trust context (verdict + degraded reasons) so the brief can be honest when data is stale/missing |

- digest dry-run ok: **True** · groups: 0 (empty here — no action signals seeded)
- monitor overall verdict: **no_data** — explains why the brief's Procore section is empty (no current data), instead of silently showing nothing.
