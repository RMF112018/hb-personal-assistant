# 04 — Projection Registry and Extractors

## Goal

Implement a field-path mapping registry and extraction layer that is deterministic, testable, and complete.

## Required functionality

- Register endpoint-specific extraction plans.
- Extract scalar fields.
- Expand nested arrays to child rows.
- Expand nested objects to child/detail/dimension rows.
- Preserve source-quality precedence.
- Preserve raw payload linkage.
- Preserve idempotency.
- Avoid raw value emission in logs/receipts.

## Field handling rules

- Date/time fields normalize to UTC string where possible.
- Money fields preserve numeric text and currency where available.
- Quantity/unit fields preserve quantity, unit cost, UOM, and calculation strategy where available.
- Person/company fields preserve display name and stable IDs/hashes when available.
- Cost code/WBS fields preserve flat code, path codes, segment ids, segment names, and segment type.
- Custom fields preserve key/label/value/type where available.
- Attachments preserve metadata only; no signed URLs or raw content bodies in evidence/output.
- Sidecar JSON is allowed only inside local DB tables and only when field shape is endpoint-specific or variable. Sidecar must be linked and covered by projection matrix; it is not a substitute for known high-value scalar fields.

## Completion gate

A new test must fail if a fixture payload contains an unmapped business field path.
