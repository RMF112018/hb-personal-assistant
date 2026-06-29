# Tool Registry Proof

- Installed FastMCP supports tool annotations and `_meta`.
- Installed FastMCP does not support request-aware per-client `list_tools` filtering.
- Core tools annotated:
  - `list_directory`: read-only, `obsidian.read`
  - `search_vault`: read-only, `obsidian.read`
  - `read_file`: read-only, `obsidian.read`
  - `create_note`: write, `obsidian.write`
  - `patch_note`: destructive replacement, `obsidian.write`
- ChatGPT read-only behavior is enforced through DCR default `obsidian.read`, OAuth scope checks, and existing write-policy gates.

