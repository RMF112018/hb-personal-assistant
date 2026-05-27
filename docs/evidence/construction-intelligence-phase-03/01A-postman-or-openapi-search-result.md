# 01A — Postman / OpenAPI Search Result (Prompt 01A)

**Run date:** 2026-05 (during Prompt 01A execution)
**Package context:** HB Construction Intelligence Phase 03 Procore Integration Package (exact Downloads path per query + 15_Addendum)

## Search Performed

- web_search: "Procore REST API Reference official developers.procore.com List Projects RFIs Submittals Change Events Commitments Invoices"
- Additional targeted searches for specific endpoints and "Procore OpenAPI" / "Procore Postman collection official".

## Results

**No public, official, machine-readable Postman collection or OpenAPI/Swagger export was discoverable** (consistent with the finding documented in the package's own 15_Procore_API_Endpoint_Reference_And_Call_Structure_Addendum.md during package preparation).

The authoritative source remains the **Procore Developer Portal REST API Reference**:
- Primary hub: https://developers.procore.com/reference/rest (supports ?version=latest, v1.0, v1.1, v2.0 on individual resources).
- Base hosts: https://api.procore.com (production), https://api-sandbox.procore.com (sandbox).
- Common requirements: OAuth 2.0 Bearer token + often `Procore-Company-Id: 5280` header.
- Pagination/filtering: page, per_page, filters[field], updated_at, sort — consistent across most resources.
- Responses: JSON, frequently paginated with metadata.

### Concrete Official Reference URLs (from search, used for reconciliation in 01A)

- Projects: https://developers.procore.com/reference/rest/projects?version=1.1 (or /rest/v1.1/projects)
- RFIs: https://developers.procore.com/reference/rest/rfis?version=latest (/rest/v1.0/projects/{project_id}/rfis)
- Submittals: https://developers.procore.com/reference/rest/submittals?version=latest
- Change Events: https://developers.procore.com/reference/rest/change-events
- Commitments / Commitment Contracts: https://developers.procore.com/reference/rest/commitment-contracts?version=2.0 (newer recommended v2.0 paths)
- Invoices / Requisitions / Payment Applications: Split across requisitions, payment_applications, and commitment-related resources (see official pages for exact current paths).

Full details, parameters, response schemas, permissions, and changelogs are on the individual reference pages (the pages are the source of truth; the site is JS-rendered and not a single machine-readable export).

## Conclusion for Prompt 01A

- The candidate catalog in the materialized `procore_endpoint_reference.phase03_unverified.seed.yaml` (brought in from the Phase 03 package) uses modern /rest/v1.x paths that align with the official reference.
- The repo's active `procore_endpoint_contract.seed.yaml` was enriched in 01A to use the verified modern paths for the original required categories, with notes recording the official source + "Prompt 01A" verification.
- No official machine-readable export exists for automated import. Future prompts (or operator manual work with the package's Postman skeleton) can use the reference pages + the materialized unverified catalog + redacted dry-run evidence for further expansion.
- See the main 01A verification report and the endpoint-reference matrix for the reconciled set and pending candidates.

**End of search result.**
