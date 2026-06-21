# PO Projection Drift Summary

- 5/5 financial-only PO keys classified as **commitment_backed_po** (expected enrichment)
- Projects: caretta (3), pga-modern-garage (1), rybovich (1)
- Projection path: `procore_commitment_projection.py::_project_purchase_order`
- Parity gate suppresses misleading `missing_source_keys` warnings for commitment-backed keys
- Evidence: `../purchase-order-projection-drift-evidence.json`