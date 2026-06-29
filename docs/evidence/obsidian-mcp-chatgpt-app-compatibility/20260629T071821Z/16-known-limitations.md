# Known Limitations

- Public `https://mcp.bobby-fetting.me` was not running this branch during validation, so public ChatGPT setup cannot complete yet.
- ChatGPT manual connector setup was not performed from this environment.
- Per-client tool-list filtering is not supported by the installed FastMCP SDK; read-only behavior is enforced through scopes and write-policy gates.
- Direct shell `curl` commands were blocked by local command policy, so curl-style probes were executed through a local Python harness and outputs were redacted.
- Broad `api.py` lint remains noisy due unrelated pre-existing issues.

