# Reference — Raw Content Boundary

## Allowed Local Inputs

Allowed only for bounded local model context or explicit raw-local preview:

- subject
- sent/received timestamps
- sender/recipient role hints
- candidate/watch IDs
- source aliases
- sanitized bounded body text snippets
- raw excerpt hash

## Always Excluded

- attachments
- attachment text
- body HTML
- inline images
- URLs
- signed URLs
- download URLs
- join URLs
- tokens
- secrets
- API keys
- raw prompts in persistence/evidence
- raw model responses in persistence/evidence

## Preview Boundary

Raw-local preview:

- explicit flag only
- terminal/local-only
- redacted
- bounded
- not JSON by default
- never evidence
- never persisted

## Persistence Boundary

Persist only:

- hashes
- structured/redacted enriched fields
- source refs
- review status
- model/task metadata

Never persist raw content.
