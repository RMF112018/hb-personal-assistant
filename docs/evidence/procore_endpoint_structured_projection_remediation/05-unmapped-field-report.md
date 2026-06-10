# 05 — Unmapped Field Report

Mechanical completeness across all endpoints with full raw payloads.

- **unmapped_primary_business_fields = 0**
- **unmapped_nested_business_fields = 0**
- **unknown_business_field_paths = 0**

Every endpoint with available full raw payloads has zero unmapped/unknown business field paths.

## Sidecar-justified endpoints (amendment 1: >25% sidecar-only)

- **prime-contracts** (26.6% sidecar-only): Sidecar holds only secondary nested contractor/vendor company-profile attributes (address, phone, logo, website, labor_union, project_ids[], profile attachments). High-value contract financials and vendor/contractor identity are first-class columns; these profile attributes are polymorphic company-directory metadata with no contract-analytics value.
- **purchase-order-contracts** (32.3% sidecar-only): Sidecar is dominated by per-tenant dynamic custom-field DEFINITION metadata (custom_field_<id>.data_type) and origin_data blobs. Custom-field ids are project-specific and polymorphic, so their definition metadata cannot be fixed columns. Standard PO business and financial fields are first-class columns.

Endpoints with no full payload this pass (`no_full_payload_available`): `activities`, `budget-change-line-items`, `budget-detail-columns`, `budget-detail-rows`, `budget-details`, `change-event-comments`, `commitment-change-order-line-items`, `daily-log-accident-review-routed`, `daily-log-delays-review-routed`, `daily-log-dumpster`, `daily-log-safety-violation-review-routed`, `meeting-detail`, `meeting-topics`, `payment-applications`, `prime-contract-attachments`, `purchase-order-detail-line-items`, `rfi-responses`, `rfq-quotes`, `rfq-responses`, `subcontractor-invoice-contract-items`, `submittal-packages`, `submittal-responses`
