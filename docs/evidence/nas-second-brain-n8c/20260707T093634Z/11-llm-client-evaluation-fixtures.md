# 11 — LLM-Client Source-Access Evaluation Fixtures (deterministic, no live LLM)

`tests/test_source_connector_eval.py` encodes the phase brief's realistic client questions as a reusable
evaluation package and asserts, via a deterministic intent scorer over the REAL registered tool descriptions,
that the client-facing descriptions route source-file questions to the new `assistant_source_*` tools —
testing routing INTENT (source tool must out-score the vault-note AND source-card baselines), not mere
keyword coverage.

## Encoded scenarios (from the brief)
Show source-root structure · find contract PDFs under NAS project source folders · search source-file
contents for a payment-application term · open metadata for a source-file result · show neighboring files ·
next page of source-file results · find files under a specific `source_root_key` · read an original source
file · open an Obsidian vault note · open the generated source card only if it exists.

## Assertions (all pass)
- `test_all_source_tools_have_disambiguating_descriptions` — every tool's description says SOURCE + FILE and
  contrasts with vault notes / cards; the search tool names concrete types (pdf/contract/invoice).
- `test_source_prompts_route_to_source_tools` — for each source-file prompt, the best source tool out-scores
  BOTH the vault-note and source-card baselines.
- `test_specific_source_tool_selection` — where the brief names a tool, deterministic argmax selects it
  (roots_list / file_search / file_metadata / files_list / file_read).
- `test_vault_and_card_prompts_do_not_route_to_source_tools` — a vault-note prompt prefers the vault baseline;
  a source-card prompt prefers the card baseline; neither is won by a source tool.
- `test_scenarios_cover_the_brief` — ≥9 scenarios covering all three object types.

## For later live validation
This is a deterministic package Bobby can reuse during live LLM-client testing (no live LLM required in
N8C-12). Acceptance criterion met: the descriptions + response shapes make source-file tools the obvious
choice for source-file questions.
