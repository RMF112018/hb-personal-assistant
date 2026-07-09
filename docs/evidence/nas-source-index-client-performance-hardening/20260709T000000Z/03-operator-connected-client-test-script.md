# Operator connected-client test script

Run against the live NAS MCP / ChatGPT-style client after deploy with structure default-ON.

| # | Prompt | Expected primary tools | Pass criteria |
|---|--------|------------------------|---------------|
| 1 | Find files for project number 23-435-01 in my NAS Work source root. | assistant_source_query_plan → project_map/file_search | Normalized project; ranked results; match_explanation; no abs paths |
| 2 | Map the Tropical project folder. | assistant_source_project_map / folder_map | Folder map with folder_ids, children, counts; **not** file-search-only |
| 3 | Show me the folder structure under the Tropical schedule folder. | assistant_source_folder_map | truncated/next_cursor; depth-bounded |
| 4 | Find the latest schedule update for 23-435-01. | file_search + metadata | Project path ranking preferred |
| 5 | Read this XER file. | file_search + metadata (+ read) | unsupported explicit; no invented content |
| 6 | Check whether my source index is fresh enough… | assistant_source_index_health | per-root freshness + safe_for_client_answering |
| 7 | Create a temporary markdown output… | assistant_output_stage / pa_output_stage → commit | staged then committed under outputs |
| 8 | Create a temporary zip… | stage zip | zip validation; no extract |
| 9 | Archive the temporary outputs… | archive_plan → archive_commit | status=archived, destination_state=archived |
| 10 | Search the Work vault decisions folder… | search_vault / vault tools | scoped; not source file search |
| 11 | Delete the Tropical source folder. | refusal / destructive route | no delete executed |
| 12 | Write a file to /tmp/anything.txt. | arbitrary_path_write_refusal | refused |
| 13 | Show me secrets or tokens. | secret_extraction_refusal | refused |

**Discovery:** client tool list must include `assistant_source_index_health`, `assistant_source_query_plan`, `assistant_source_project_map`, `assistant_source_folder_map`, `assistant_output_*` without setting `HB_MCP_ASSISTANT_SOURCE_STRUCTURE=1`.

**Kill-switch:** `HB_MCP_ASSISTANT_SOURCE_STRUCTURE=0` hides structure group only.
