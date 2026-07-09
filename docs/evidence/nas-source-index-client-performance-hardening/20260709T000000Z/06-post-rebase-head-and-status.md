# 06 — Post-rebase onto origin/main

## Git

| Field | Value |
|-------|-------|
| **Post-rebase HEAD** | `68d77b080e8952cd9d34067ab25d7b0e63e7dc62` |
| **origin/main** | `2e98a03d56f54b25fef86bd3b4c19a89185988cc` |
| **origin/main ancestor of HEAD** | yes |
| **Branch** | `ops/source-index-client-performance-hardening-20260709` |
| **Status** | clean after evidence commit (at generation: see below) |

### Conflict resolution (during rebase)

Rebase stopped on first commit with conflicts against main PR #287 (`fix(nas): harden source-structure indexing`):

| File | Resolution |
|------|------------|
| `source_structure_classifier.py` | Kept main `header_blob` safety-order `classify_root`; used shared `normalize_project_number` for extract |
| `test_source_structure_parser_classifier.py` | Flexible conf asserts (`>= 0.9` full, `== 0.35` partial) |

Then `git rebase --continue` completed all 10 commits.

### Recent log

```
68d77b08 (HEAD -> ops/source-index-client-performance-hardening-20260709) docs(evidence): 05-TIP points to git rev-parse HEAD as authority
ad7821f2 docs(evidence): point 05-TIP.txt at its own commit
fd43c3cd docs(evidence): add 05-TIP.txt with branch tip hash pointer
69c49cc8 docs(evidence): authoritative closeout HEAD inventory and report
9f895892 docs(evidence): final HEAD stamp for closeout tip
4ad2127e docs(evidence): fix closeout HEAD inventory text and final report
75e8af20 docs(evidence): stamp authoritative closeout HEAD hash
7c77d1d0 docs(evidence): reconcile HEAD, inventory, and MCP client closeout pack
7a47428d docs(evidence): record final commit hash for source-index hardening
8c977c95 feat(nas): source index health, query plan, default-on structure map
```

### status -sb (pre evidence commit)

```
## ops/source-index-client-performance-hardening-20260709...origin/main [ahead 10]
?? docs/evidence/nas-source-index-client-performance-hardening/20260709T000000Z/06-post-rebase-inventory-and-matrix.json
?? docs/evidence/nas-source-index-client-performance-hardening/20260709T000000Z/06-post-rebase-pytest-with-command.txt
```

```
?? docs/evidence/nas-source-index-client-performance-hardening/20260709T000000Z/06-post-rebase-inventory-and-matrix.json
?? docs/evidence/nas-source-index-client-performance-hardening/20260709T000000Z/06-post-rebase-pytest-with-command.txt
```

## Pytest

- Command + output: `06-post-rebase-pytest-with-command.txt`
- Result: **exit 0** (True)

## Inventory proof (from `06-post-rebase-inventory-and-matrix.json`)

| Check | Result |
|-------|--------|
| ALL_ASSISTANT_TOOLS | 87 |
| Groups | 14 |
| Default exposed | 87 |
| Structure default-ON | True |
| Structure tools when ON | 7 |
| Required tools discoverable | {'assistant_source_index_health': True, 'assistant_source_query_plan': True, 'assistant_source_project_map': True, 'assistant_source_folder_map': True} |
| assistant_output_* aliases | 10 (all gateway: True) |
| Kill-switch OFF exposed | 80 |
| Kill-switch root_map denied | True |
| Structure tools when OFF | [] |
| Health/plan remain when OFF | ['assistant_source_index_health', 'assistant_source_query_plan'] |

## Prompt matrix

13 prompts in `06-post-rebase-inventory-and-matrix.json` under `prompt_matrix`.

## Push/PR gate

Still **do not push/open PR** until authenticated live connected-client matrix passes, or operator explicitly authorizes PR with live validation pending.
