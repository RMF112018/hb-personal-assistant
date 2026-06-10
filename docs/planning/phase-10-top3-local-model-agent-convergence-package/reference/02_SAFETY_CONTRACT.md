# Reference — Safety Contract

## Allowed

- Local-only Ollama model calls.
- DB-copy validation.
- Capped, idempotent local DB writes on DB copies during validation.
- Production DB reads.
- Redacted browser/Obsidian/status outputs under user-local non-repo paths.
- Review-safe persistence of structured V45 fields.

## Disallowed

- Cloud LLM calls.
- Email send/draft.
- Calendar mutation.
- Procore writeback.
- Microsoft Graph writeback.
- MCP raw exposure.
- External writeback.
- Production DB mutation during validation.
- Raw body/prompt/response persistence.
- Unsafe content in repo artifacts.

## Required labels

- Final rendered model-enriched section label: **Model Enriched Intelligence**.
- Any model-enriched content must be advisory/source-linked.
- Low-confidence or pending-review items must remain clearly labeled.
