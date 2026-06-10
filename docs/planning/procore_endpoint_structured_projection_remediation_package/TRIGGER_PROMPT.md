Execute the objective defined at:

`docs/planning/procore_endpoint_structured_projection_remediation_package/README.md`

You are working in `/Users/bobbyfetting/hb-personal-assistant`.

Create and use branch:

`fix/procore-endpoint-specific-structured-projections`

Run the prompt chain in `docs/planning/procore_endpoint_structured_projection_remediation_package/prompts/` in numeric order.

The objective is implementation, not planning only: audit all Procore endpoints/tables and remediate the schema/projection engine so every primary and nested business field observed in full raw Procore payloads is projected into endpoint-specific local raw/structured content tables, child/detail tables, dimension/bridge tables, or documented lossless sidecars. Do not consider the work complete until mechanical evidence proves zero unmapped primary and nested business fields for every endpoint with available full raw payloads.

Hard constraints:
- No raw payload bodies, secrets, signed URLs, `.db`, `.sqlite`, `.env`, or cache artifacts may be committed.
- No production DB mutation during validation; use `/tmp` copies and prove production sha256 unchanged.
- Preserve PR #18 full raw payload persistence and source-quality precedence.
- Preserve no external writeback.
- Commit and push the implementation branch only after validation and evidence are complete.
