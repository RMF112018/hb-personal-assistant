# Final Output — `daily-brief mcp-packet --no-json`

Command (disposable temp DB):
```
python -m hb_assistant.cli.main second-brain daily-brief mcp-packet \
  --db /tmp/phase10_mcp_packet_smoke.sqlite --as-of 2026-06-09T05:00:00-04:00 --no-json
```
Exit code: 0. Captured stdout (operator Markdown):
```
# MCP Context Packet

_Contract phase10-mcp-1.0 · purpose `daily_brief_local_agent_context` · generated 2026-06-09T05:00:00-04:00 · brief 2026-06-09_

## Candidate summaries (counts only)
- open commitments: {'accepted_tasks': 0, 'accepted_commitments': 0, 'follow_up_watch_items': 0}
- candidates by section: {}
- relationships: 0 · procore signals: 0 · calendar: 7

## Caps applied
- {'max_candidates_per_section': 12, 'max_meetings': 15, 'max_relationships': 8, 'max_procore_groups': 20, 'max_tasks': 15}

## Omitted raw categories
- raw_email_bodies, raw_document_text, raw_calendar_payloads, raw_procore_payloads, raw_model_prompts, raw_model_responses, html_bodies, signed_urls, download_urls, join_links, bearer_tokens, attendee_arrays, email_address_dumps

## Freshness / quality warnings
- no Procore action signals available for this run
- no accepted tasks/commitments or follow-up watch items available

## Safety
- {'read_only': True, 'metadata_only_summaries': True, 'source_refs_hashed': True, 'no_raw_content': True, 'no_external_writeback': True, 'fail_closed_on_forbidden_content': True, 'deterministic': True}
```

Notes:
- Counts-only / metadata-only; raw-free. The "## Omitted raw categories" line lists **category
  labels** (`signed_urls`, `download_urls`, `join_links`, `bearer_tokens`, …) that the contract
  explicitly excludes — these are safe labels, NOT actual tokens/URLs (documented safe matches).
- The fail-closed forbidden-content gate passed (exit 0, `no_raw_content: True`). On a detected
  leak the packet would withhold context and exit 3.
- Temp DB was created fresh and removed after capture; production DB untouched.
