# MCP Capability Profiles

The canonical capability registry defines startup-static MCP profiles. These
counts are assertions checked against the generated registry; the registry and
its operator-authorized CSV input remain the semantic authority.

| Profile | Direct FastMCP tools | Rule |
|---|---:|---|
| `frontier-v1` | 12 | Gate-enabled members with `direct_exposure=true`. |
| `legacy-v12` | 185 | Explicit compatibility exception: every gate-enabled legacy member. |
| `internal` | 70 | Gate-enabled members with `direct_exposure=true`. |

Historical tool-count statements elsewhere describe their named historical
surface and must not be interpreted as current profile counts.
