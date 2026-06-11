# 05 — Consumer Read Models and Model Context (Pass 2)

Every downstream consumer now routes through a single precedence-aware read model so the final
structured projection layer is preferred over raw-landing and legacy/redacted metadata by
source-quality rank, and a lower-quality row can never silently downgrade consumer context.

## Read model (`construction/email_calendar/read_models.py`)

`select_email_message_context` / `select_thread_context` / `select_event_context` return typed,
**redacted-safe** objects carrying `selected_source` + `source_quality` + business metadata +
child collections (recipients/attendees) + a `body_ref` link. Selection tiers (highest wins):

```
structured_full  > structured_preview > structured_legacy > raw_landing > legacy_metadata > none
```

Raw body/agenda text is never on the object; it is fetched local-private only via `load_body(...)`,
which writes a `raw_content_access_events` audit row. Backed by new `ConstructionStore` structured
accessors (`get_email_message_structured`, `get_event_structured`, `list_*_structured`, child
fetchers).

## Consumers rewired

| consumer | change |
|---|---|
| `email/endpoints.py`, `calendar/endpoints.py` | attach `_selected_source` + `source_quality` from the read model on the effective-raw path (structured preferred; selected tier visible) |
| `meeting_prep/brief_builder.py::_section_meeting_context` | agenda/attendee detail now sourced from the structured event projection; the persisted `section_redacted` carries availability FLAGS + attendee roles + source-quality, and **no longer** the agenda body or join URL (a redaction improvement) |
| `second_brain/local_ai/raw_context.py` | model-context packets record `structured_projection_preferred: true` + `source_quality_distribution` from the structured layer |
| `second_brain/local_ai/relationship_scoring.py::find_email_calendar_relationships` | structured-backed pairs preferred + tagged with each side's structured source-quality |
| `second_brain/local_ai/raw_followup_window.py` | window meta tagged with the best structured source-quality backing it |
| `retrieval/retriever.py` | new `retrieve_email_calendar_structured` — ranks structured rows, returns redacted results (hashed subject ref + source-quality + availability flags), prefers higher source-quality |

## Precedence proof (tests, `tests/test_email_calendar_consumer_read_models.py`)

```text
structured selected ahead of raw/legacy ............... PASS
falls back to raw_landing ONLY when no structured row .. PASS
lower-quality cannot downgrade consumer context ....... PASS (downgraded raw -> structured stays graph_full_body)
read-model objects carry no body / join URL ........... PASS
load_body audits the raw read (access event written) .. PASS
email/calendar endpoints expose selected_source ....... PASS
meeting prep uses structured + no agenda/join leak .... PASS
model-context packet records structured distribution .. PASS
relationships tagged structured ....................... PASS
retrieval returns redacted (hashed subject) ........... PASS
```

## `/tmp` DB-copy consumer summary (real production rows)

```text
consumer_source_summary:
  email_message   : {structured_legacy: 1}
  calendar_event  : {structured_legacy: 117}
```

Consumers select the **structured projection** for all 118 production rows (tier
`structured_legacy` because these pre-V49 rows carry the honest `metadata_only` default; they are
reclassified to `structured_full` on the next operator raw re-ingest). No consumer falls back to
raw-landing or legacy metadata when a structured row exists.
