# Source: HB Construction Intelligence Phase 03 package (resources/templates/ — Prompt 10 templates). Package manifest sha: 3fc1b8c9d92c61ef201a41116e75165f78320a20582aa080acb356dec22b7257. Copied for deterministic rendering. DO NOT EDIT MANUALLY.

# Procore Endpoint Audit — {{ project_name }}

Run ID: `{{ run_id }}`
Mode: `{{ mode }}`
Generated: `{{ generated_utc }}`

| Endpoint | Category | Status | Verdict | Notes |
| --- | --- | --- | --- | --- |
{{ endpoint_rows }}
