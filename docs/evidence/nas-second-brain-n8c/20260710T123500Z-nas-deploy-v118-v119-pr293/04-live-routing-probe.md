# Live routing probe — operator 2026-07-10

```bash
ssh -t hb-nas 'sudo /usr/local/bin/docker exec hb-personal-assistant-mcp python3 -c "..."'
```

## Raw output

```text
runtime_commit= 14dfc3a0e007475543e19f1d8efd999b23f3e28b
Do not promote anything. -> context_preflight not_authorized False
Stage this for review. -> stage_artifact_proposals missing_arguments False
Search my work files. -> source_file_search None True
Search the vault for meeting notes. -> vault_note_search None True
Promote the approved artifact. -> apply_canonical_promotion missing_arguments False
```

## Acceptance (Phase 10)

| Prompt | Workflow | Blocker | Executable | Pass |
| --- | --- | --- | --- | --- |
| Do not promote anything. | `context_preflight` (≠ promotion) | `not_authorized` | False | yes — no promotion workflow |
| Stage this for review. | `stage_artifact_proposals` | `missing_arguments` | False | yes — not `approval_required` |
| Search my work files. | `source_file_search` | None | True | yes — NAS source, not vault |
| Search the vault for meeting notes. | `vault_note_search` | None | True | yes — vault workflow |
| Promote the approved artifact. | `apply_canonical_promotion` | `missing_arguments` | False | yes — not executed |

All required live prompt-routing acceptance checks **PASS**.