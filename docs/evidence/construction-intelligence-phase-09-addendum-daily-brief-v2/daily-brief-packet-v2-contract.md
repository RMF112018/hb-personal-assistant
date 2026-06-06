# Daily Brief V2 Handoff Packet Contract (`DailyBriefHandoffPacketV2`)

**Package:** HB_Construction_Intelligence_Phase_09_Addendum_Daily_Brief_V2_Executive_Utility_Hardening
**Contract version:** 1.1.0-phase-09-addendum-v2 (Prompt 01 split + Prompt 02 record-level enrichment)

The authoritative machine contract is `daily-brief-packet-v2-contract.json` (a copy of the registered
resource `phase_09_daily_brief_handoff_packet_v2_contract.json`).

## Two halves

- `render_payload` — user-facing, brief-ready data only.
- `governance_metadata` — packet id/hash, source coverage, source refs, guardrails, rendering
  instructions, proof/receipt metadata. **Never rendered into the brief body** (separation invariant
  `forbidden_in_render_payload`).

## Count-vs-detail rule (Prompt 02)

> If the brief reports a count, it must either list the underlying records with useful detail or
> explicitly say record-level detail is unavailable. A bare count is never actionable content.

Every record-bearing section is a uniform **RecordSection**:

```
{ "count", "records", "detail_available", "detail_gap_reason", "source_family", "why_it_matters",
  "truncated"?, "total_count"? }
```

`_count_detail_ok` validity: `count == 0` (nothing to report); OR records present AND
`detail_available=true` AND `count == len(records)`; OR a positive count with no records AND
`detail_available=false` AND a non-empty `detail_gap_reason`. Truncation is explicit
(`truncated` + `total_count`) — no silent caps.

## Sections wired with real records (Prompt 02)

| Source reader | Sections |
| --- | --- |
| `calendar_event_index` (+ `calendar_event_attendees`) | `today_agenda`, `yesterday`, `calendar_activity` |
| `email_thread_summaries` | `email_activity` |
| `procore_action_signals` (`build_overdue_queue`, `get_procore_action_signals`) | `next_7_days`, `schedule` |

## Detail-unavailable domains (Prompt 02)

`rfis`, `submittals`, `punch`, `procurement` have no dedicated reader yet → emitted with
`detail_available=false`, `detail_gap_reason="dedicated_reader_not_available"` and the typed
`record_field_specs` target shape (so Prompt 03+ can populate without a contract change).

## Missing-field policy (repo truth)

Fields not persisted (responsible-party / vendor **names**) are emitted `null` with a per-record
`detail_availability` reason; opaque ids are carried separately where available; `days_open`/`age`
derives only from a real start timestamp, else `null` + reason. Never fabricated.

## No raw payload

No calendar/email body, raw subject, email address, Graph/join/signed URL, token, or header is ever
emitted; the builder runs an `_assert_no_raw` backstop over the whole packet and the proof asserts no
`web_link`/URL/email patterns (plus a non-vacuous join-URL probe).

## CLI

```bash
hb-assistant second-brain daily-brief packet --date YYYY-MM-DD --version v2 --json
hb-assistant second-brain daily-brief packet-v2-proof --json
```

The proof (`daily-brief-packet-v2-proof.json`) certifies the split, source-linking, the count-vs-detail
invariant (with a non-vacuous tampered-rejection), explicit detail-unavailable domains, no raw
calendar/email payload, no final determinations, and no external writeback.
