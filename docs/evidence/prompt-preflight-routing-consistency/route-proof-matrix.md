# Route proof matrix

| prompt | workflow | family | read_auth | promote_auth | prohibitions | pass |
|---|---|---|---|---|---|---|
| Find my project notes.… | vault_note_search | assistant_navigation | True | False | [] | True |
| Read-only: identify which tool should be… | source_root_map | assistant_source_connector | False | False | ['execute', 'promote', 'stage', 'write'] | True |
| Explain which read-only Personal Assista… | source_file_search | assistant_source_connector | True | False | [] | True |
| Conduct a read-only repo-truth audit.
Do… | context_preflight | prompt_routing | False | False | ['deploy', 'execute', 'index', 'promote', 'stage', 'write'] | True |
| Search my work files.… | source_file_search | assistant_source_connector | True | False | [] | True |
| Do not promote anything.… | context_preflight | prompt_routing | False | False | ['promote'] | True |
| Search the vault for meeting notes.… | vault_note_search | assistant_navigation | True | False | [] | True |
| What did we decide about X?… | canonical_decision_retrieval | assistant_decision_memory | True | False | [] | True |
