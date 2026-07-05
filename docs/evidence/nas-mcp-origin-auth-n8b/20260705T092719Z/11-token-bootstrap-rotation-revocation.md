# 11 — Token Bootstrap / Rotation / Revocation

Operator CLI: `python -m hb_assistant.nas_mcp.origin_auth_cli` (standalone argparse — does
**not** import the full Typer app / forbidden FastAPI backend).

## Commands
```
# mint (raw token printed ONCE to stdout; metadata notice on stderr)
python -m hb_assistant.nas_mcp.origin_auth_cli create-token \
    --client claude --label "Claude Desktop" --actor bfetting --expires-days 30 \
    [--tier read] [--allowed-tool hb_mcp_status --allowed-tool hb_root_list]

python -m hb_assistant.nas_mcp.origin_auth_cli list-tokens          # no raw secrets
python -m hb_assistant.nas_mcp.origin_auth_cli revoke-token --token-id <id>
python -m hb_assistant.nas_mcp.origin_auth_cli rotate-token --token-id <id> --expires-days 30
```
`--store <path>` overrides the store location (else env/config default).

## Secret handling (proven — `test_cli_create_lists_and_revokes`)
- The **raw token is emitted only to stdout, exactly once**, with a "store it now, not
  recoverable" notice on stderr. It is **never** written to the store file in plaintext
  (store holds only `sha256(token)` + metadata) and **never** re-shown by `list-tokens`.
- `list-tokens` prints `token_id / client / label / actor / expiry / revoked / tier /
  allowed_tools / fingerprint` only.
- `revoke-token` flips `revoked=true`; a rotated/revoked token fails `validate` immediately.

## Operator storage rule
Put the printed bearer into `local-sensitive/` or a password manager. It must never enter
git, committed evidence, or logs. Evidence records tokens by **label + fingerprint** only.

## Status
Implemented and tested (so this phase is not merely "design documented"). Full OAuth 2.1
issuance flow remains deferred — bearer-token bootstrap satisfies the operator workflow now.
