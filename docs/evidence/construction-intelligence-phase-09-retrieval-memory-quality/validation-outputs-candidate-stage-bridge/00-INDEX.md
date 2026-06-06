# Validation Outputs — Candidate Staging Bridge (live acceptance demonstration)

Live run of the issue's acceptance sequence on the operator DB, demonstrating the
`preview → stage → accept` bridge end-to-end. The target is the benign tier-1 system fact
`mcp_562433b32e4190a63db894907846e1e0` (`system:local_first_posture`) — reversible via
`memory supersede` / `memory reject`.

| File | Command | Result |
|---|---|---|
| 01 | `memory candidates build` | target id present in preview |
| 02 | `memory candidates stage --candidate-id mcp_562433… --confirm` | **staged=true, persisted=true, id preserved, tier 1** |
| 03 | `memory accept --candidate-id mcp_562433… --confirm` | **accepted=true** (memory_id created, no blocks) — previously failed `candidate not found` |
| 04 | `memory list --status accepted` | **count = 1** |
| 05 | `memory proof` (acceptance) | proof_passed |
| 06 | `coverage-parity-closeout` (pre-apply) | `memory_substrate_status = covered`; vector still 8 (no applied run yet) |
| 07 | `llamaindex build --apply` | **applied**; `per_family_item_count` includes `accepted_long_term_memory` |
| 08 | `no-raw-vector-index-proof` | **proof_passed** |
| 09 | `coverage-parity-closeout` (post-apply) | **`memory_substrate_status = covered`, vector-indexed family count = 9** (`accepted_long_term_memory`); `closeout_ok` + `coverage_parity_ok` true |
| 10 | `mcp no-raw-access` | proof_passed |
| 11 | `mcp no-writeback` | proof_passed |

## Outcome

The bug is fixed: a preview candidate id can be staged and then accepted. Live, the accepted system
fact made `accepted_long_term_memory` **covered** and (after apply) raised the vector-indexed family
count **8 → 9**, with all no-raw / no-writeback / MCP proofs green.
