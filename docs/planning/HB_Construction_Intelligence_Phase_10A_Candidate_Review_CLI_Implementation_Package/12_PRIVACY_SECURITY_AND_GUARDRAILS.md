# 12 Privacy, Security, and Guardrails

## Non-negotiable rules

The review CLI must never send email, mutate calendar, update Graph, update Procore, expose raw content through MCP, persist raw prompt/response/body/payloads, or persist signed URLs, download URLs, tokens, or secrets.

## Guard columns

Existing guard columns must remain zero for candidate tables and source refs:

- `raw_email_body_persisted`
- `raw_document_text_persisted`
- `raw_calendar_payload_persisted`
- `raw_procore_payload_persisted`
- `raw_prompt_persisted`
- `raw_response_persisted`
- `external_writeback_performed`
- `graph_writeback_performed`
- `procore_writeback_performed`
- `email_send_performed`
- `calendar_mutation_performed`

## Output constraints

All CLI output must be redacted/safe. Acceptable fields include candidate metadata, redacted title, redacted reason, redacted evidence snippets, source ref hashes, model profile ID, prompt template version, and guardrail flags.
