# Daily Brief V2 Handoff Packet Contract (`DailyBriefHandoffPacketV2`)

**Package:** HB_Construction_Intelligence_Phase_09_Addendum_Daily_Brief_V2_Executive_Utility_Hardening
**Prompt:** 01 — Daily Brief V2 Packet Contract · **Version:** 1.0.0-phase-09-addendum-v2

The authoritative machine contract is `daily-brief-packet-v2-contract.json` (a copy of the registered
resource `phase_09_daily_brief_handoff_packet_v2_contract.json`).

## Why V2

The V1 packet (`DailyBriefHandoffPacketV1`) is a single flat structure that mixes internal governance
metadata (source-coverage metrics, guardrails, proof/receipt internals, per-item provenance) with the
data that gets rendered into the brief body. V2 **splits the packet in two**:

- `render_payload` — user-facing, brief-ready data only.
- `governance_metadata` — packet id/hash, source-coverage metrics, source refs, guardrails, rendering
  instructions, proof/receipt metadata. **Never rendered into the brief body.**

## Shape

```
{
  "render_payload": {
    "brief_date", "portfolio_scope",
    "yesterday", "today_agenda", "next_7_days",
    "needs_attention", "focus_recommendations", "project_signals",
    "email_activity", "calendar_activity", "data_gaps"
  },
  "governance_metadata": {
    "packet_id", "packet_version", "generated_utc", "brief_date", "mode",
    "source_coverage_summary", "source_refs", "guardrails",
    "rendering_instructions", "proof_metadata", "receipt_metadata",
    "status", "degradation_mode"
  }
}
```

### Renderable item fields
`project_key`, `project_name`, `record_type`, `record_id`, `title`, `status`, `responsible_party`,
`due_date`, `start_date`, `finish_date`, `source_family`, `source_ref_hash`, `confidence_class`,
`review_tier`, `review_required`, `freshness_label`, `stale_warning`, `why_it_matters`,
`recommended_focus`, `detail_availability`.

Fields not yet sourced from the current retrieval path (`project_name`, `record_id`, `status`,
`responsible_party`, dates) are emitted as `null` and flagged in `detail_availability` — never
fabricated.

## Projection, not new retrieval

V2 is a **pure projection** over the canonical V1 packet (`_project_v2_from_v1`). It adds no new
retrieval. Sections without a current data source are emitted **empty** with an explicit `data_gaps`
entry, and are deferred to **Prompt 02 — Record-Level Enrichment**:

| Section | Status (Prompt 01) |
| --- | --- |
| `needs_attention`, `project_signals`, `focus_recommendations`, `data_gaps` | populated from V1 |
| `yesterday`, `today_agenda`, `next_7_days`, `calendar_activity`, `email_activity` | empty + data_gap |

## Guardrails (unchanged from V1)

`advisory_only`, `source_linked`, `metadata_only`, `no_raw`, `no_writeback`,
`no_final_determinations`, `claude_rendering_only`. Read-only; persists nothing; fail-closed on
missing contract or raw leakage.

## CLI

```bash
hb-assistant second-brain daily-brief packet --date YYYY-MM-DD --version v2 --json
hb-assistant second-brain daily-brief packet-v2-proof --json
```

The proof (`daily-brief-packet-v2-proof.json`) certifies: render_payload exists, governance_metadata
is separated (no governance key leaks into render), required sections exist, source refs preserved,
raw-shaped values rejected, review/stale/confidence flags preserved, final-determination language
rejected, metadata-only, no external writeback.
