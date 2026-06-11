# Raw Safety Policy

Allowed in lifecycle outputs/evidence:

- table names
- column names
- counts
- status values
- reason codes
- hash values
- source family names
- bounded redacted fields already produced by the system
- deterministic IDs
- project keys
- coverage percentages

Forbidden:

- raw email body
- raw HTML
- full raw subject/title/body text
- recipient/attendee arrays
- join URLs
- private URLs
- signed/download URLs
- tokens/secrets
- authorization headers
- raw Procore payloads/detail blobs
- raw calendar descriptions
- model prompts/responses

