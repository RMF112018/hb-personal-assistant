# 02 — Endpoint Projection Matrix Summary

- Endpoints: `37`
- Total mapped (endpoint, path) entries: `2439`
- Full matrix: `02-endpoint-projection-matrix.csv` (field paths/types/categories/destinations only; no values).

Destination kinds: `column:` (first-class column), `child:` (nested child/detail table), `sidecar:` (lossless declared JSON sidecar), `exclude:` (auth/transport secret), `structural` (container node).

| endpoint | column | child | sidecar | excluded | structural | sidecar-only % |
|---|--:|--:|--:|--:|--:|--:|
| billing-periods | 9 | 0 | 0 | 0 | 1 | 0.0 |
| budget-change-history | 8 | 0 | 0 | 0 | 1 | 0.0 |
| budget-modifications | 9 | 0 | 0 | 0 | 1 | 0.0 |
| budget-views | 10 | 0 | 1 | 0 | 3 | 9.1 |
| change-events | 170 | 5 | 31 | 0 | 44 | 15.0 |
| commitment-attachments | 5 | 0 | 0 | 0 | 1 | 0.0 |
| commitment-change-orders | 45 | 0 | 0 | 0 | 4 | 0.0 |
| commitment-compliance | 20 | 2 | 3 | 0 | 3 | 12.0 |
| commitment-contracts | 49 | 0 | 0 | 0 | 5 | 0.0 |
| commitment-line-items | 15 | 0 | 0 | 0 | 2 | 0.0 |
| daily-log-dcrs | 41 | 1 | 4 | 0 | 7 | 8.7 |
| daily-log-deliveries | 28 | 1 | 3 | 0 | 5 | 9.4 |
| daily-log-inspections | 37 | 1 | 3 | 0 | 5 | 7.3 |
| daily-log-manpower | 47 | 1 | 6 | 0 | 6 | 11.1 |
| daily-log-notes | 31 | 1 | 3 | 0 | 5 | 8.6 |
| daily-log-visitor | 20 | 0 | 4 | 0 | 4 | 16.7 |
| daily-log-weather | 26 | 0 | 3 | 0 | 3 | 10.3 |
| inspection-items | 45 | 1 | 12 | 0 | 11 | 20.7 |
| inspection-sections | 5 | 0 | 0 | 0 | 1 | 0.0 |
| inspections | 99 | 4 | 11 | 0 | 12 | 9.6 |
| meetings | 22 | 0 | 0 | 0 | 1 | 0.0 |
| observations | 59 | 1 | 11 | 0 | 8 | 15.5 |
| prime-change-order-line-items | 14 | 0 | 0 | 0 | 2 | 0.0 |
| prime-change-orders | 43 | 0 | 0 | 0 | 4 | 0.0 |
| prime-contract-line-items | 11 | 0 | 0 | 0 | 2 | 0.0 |
| prime-contracts | 91 | 0 | 33 | 0 | 8 | 26.6 |
| projects | 86 | 7 | 20 | 0 | 32 | 17.7 |
| punch-items | 80 | 3 | 6 | 0 | 12 | 6.7 |
| purchase-order-contracts | 108 | 1 | 52 | 0 | 53 | 32.3 |
| purchase-order-line-items | 45 | 1 | 6 | 0 | 10 | 11.5 |
| rfis | 83 | 3 | 4 | 0 | 11 | 4.4 |
| rfqs | 195 | 4 | 27 | 0 | 30 | 11.9 |
| schedules | 16 | 0 | 0 | 0 | 1 | 0.0 |
| subcontractor-invoice-change-order-items | 32 | 0 | 0 | 0 | 3 | 0.0 |
| subcontractor-invoice-contract-detail-items | 29 | 0 | 0 | 0 | 3 | 0.0 |
| subcontractor-invoices | 66 | 1 | 2 | 0 | 9 | 2.9 |
| submittals | 108 | 3 | 15 | 0 | 18 | 11.9 |
