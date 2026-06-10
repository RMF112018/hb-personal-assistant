# Reference — Evidence File Contract

All evidence must be committed-safe and raw-free.

## Allowed evidence content

- command names
- exit codes
- counts
- hashes
- redacted paths
- schema version numbers
- table/column names
- source ID hashes
- candidate IDs
- safe route metadata
- safe reason codes
- boolean proof results

## Disallowed evidence content

- raw email/document/calendar/Procore body text
- raw prompts
- raw model responses
- unsafe HTML
- full URLs
- signed/download/join links
- credential-shaped strings
- private payloads
- local absolute paths unless redacted to `~/...`

## Required evidence pattern

Each prompt must create or update at least one evidence file and must append a short note to the final evidence index.
