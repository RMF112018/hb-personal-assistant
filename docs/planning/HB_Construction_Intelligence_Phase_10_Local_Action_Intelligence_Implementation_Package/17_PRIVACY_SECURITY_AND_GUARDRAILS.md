# 17 Privacy, Security, and Guardrails

## Guardrails

- Local-first. No external LLM/API dependency is required for Phase 10.
- No Graph writeback, Procore writeback, email send, calendar mutation, Teams/Slack/SMS/push delivery, or source-system update.
- No raw email body, raw calendar payload, raw Procore payload, raw document text, raw model prompt, raw model response, signed URL, download URL, token, secret, or arbitrary path persistence.
- Local model outputs are advisory candidate records unless explicitly accepted by the user.
- High-stakes items involving contract, legal, financial, payment, claim, entitlement, safety, or schedule impact are signals requiring human review, never determinations.
- Model direct access to Graph, Procore, local filesystem outside allowlisted folders, arbitrary SQL, subprocess, browser, network, or MCP write tools is prohibited.
- Structured model output must validate against a JSON Schema/Pydantic contract before any database write.
- Every accepted candidate must retain source references, confidence, model profile, prompt/template version, input window metadata, and review status.
- Dev and Production outputs, receipts, vector stores, job queues, and Obsidian writes must remain isolated by environment profile.


## Prompt injection posture

Local model input may include externally authored text. Treat it as untrusted data.

Do not allow source content to instruct the model to:

- change system prompts;
- ignore schemas;
- reveal secrets;
- call tools;
- access files;
- send messages;
- mutate calendar/Procore/Graph;
- write arbitrary Obsidian notes.

## Persistence posture

Persist only:

- hashes;
- bounded redacted excerpts when allowed;
- structured candidate fields;
- model/profile identifiers;
- prompt/template versions;
- source refs;
- confidence;
- review status;
- evidence/receipt metadata.

Do not persist raw input windows or raw model responses.
