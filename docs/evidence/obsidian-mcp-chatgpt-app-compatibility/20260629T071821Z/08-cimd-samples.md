# CIMD Samples

CIMD was intentionally not implemented in this change.

- `client_id_metadata_document_enabled`: `false`
- `client_id_metadata_document_supported`: not advertised in OAuth metadata
- Rationale: DCR is implemented now; CIMD should only be advertised after SSRF-hardened fetch, cache, and validation behavior is implemented and tested.

