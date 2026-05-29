# Phase 05 Prompt 00 — Rebaseline & Financial Endpoint Source Inventory (pointer)

> This filename is the "Required Output Files" alias for the canonical deliverable. To
> avoid two diverging copies, the full content lives in one place:
>
> **→ [`00-repo-truth-rebaseline-and-financial-endpoint-source-inventory.md`](./00-repo-truth-rebaseline-and-financial-endpoint-source-inventory.md)**

## Quick summary

- **`HEAD` = `74d89d54c1546f10e0a2f44bf426e4eba5d8659a`** — a benign descendant of the
  expected baseline `0d8a1f6` (Phase 04B closeout), two doc-only commits ahead. No
  financial code changed since closeout.
- **32 financial endpoints** inventoried from the attached package reference, grouped into
  the 6 prompt groups (owner contracts 6, commitments 6, purchase orders 3, invoices 5,
  RFQs/change events 5, budget 7). **1,604 field paths, names + types only.**
- **Zero financial endpoints/normalizers/tables exist in code today** — all 32 are net-new
  for Phase 05.
- Duplicate-counting risks documented: commitments(v2) vs purchase-orders(v1),
  `budget-details` unresolved path (fail-closed), parent/child line-item fan-out, and
  multi-family change-order surfaces.

## Companion artifacts

- [`phase05-financial-endpoint-inventory.json`](./phase05-financial-endpoint-inventory.json) — full field-level inventory (32 endpoints, 1,604 paths).
- [`phase05-financial-normalizer-coverage-baseline.md`](./phase05-financial-normalizer-coverage-baseline.md) — zero-baseline normalizer coverage matrix.
