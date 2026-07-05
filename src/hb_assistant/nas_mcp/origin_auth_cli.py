"""Operator CLI for NAS MCP origin-auth tokens (create / list / revoke / rotate).

Standalone argparse tool — intentionally does NOT import the full hb-assistant Typer app
(which would pull in the FastAPI backend forbidden in the NAS process). Run as::

    python -m hb_assistant.nas_mcp.origin_auth_cli create-token --client claude \\
        --label "Claude Desktop" --actor bfetting --expires-days 30

Secret handling: the raw token is printed to stdout EXACTLY ONCE on create/rotate, with a
"store it now" notice. It is never shown again by ``list-tokens`` and never persisted in
plaintext. Put the printed value into ``local-sensitive/`` or a password manager only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .config import NasMcpConfig
from .origin_auth import ALLOWED_TOKEN_CLIENTS, OriginAuthTokenStore, resolve_token_store_path


def _store(args: argparse.Namespace) -> OriginAuthTokenStore:
    if args.store:
        return OriginAuthTokenStore(Path(args.store))
    return OriginAuthTokenStore(resolve_token_store_path(NasMcpConfig.from_env()))


def _emit_secret(raw: str, record: dict[str, Any]) -> None:
    print("=== NAS MCP origin-auth token (shown ONCE — store it now) ===", file=sys.stderr)
    print(f"token_id   : {record['token_id']}", file=sys.stderr)
    print(f"client     : {record['client']}  label: {record['client_label']}", file=sys.stderr)
    print(f"expires_at : {record['expires_at']}", file=sys.stderr)
    print(f"fingerprint: {record['fingerprint']}", file=sys.stderr)
    print("Bearer token (copy now; not recoverable):", file=sys.stderr)
    print(raw)


def _cmd_create(args: argparse.Namespace) -> int:
    raw, record = _store(args).create_token(
        client=args.client,
        client_label=args.label,
        actor=args.actor,
        expires_days=args.expires_days,
        tier=args.tier,
        allowed_tools=args.allowed_tool or None,
    )
    _emit_secret(raw, record)
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    # No raw tokens — labels/fingerprints only.
    print(json.dumps(_store(args).list_tokens(), indent=2, sort_keys=True))
    return 0


def _cmd_revoke(args: argparse.Namespace) -> int:
    ok = _store(args).revoke(args.token_id)
    print(json.dumps({"token_id": args.token_id, "revoked": ok}))
    return 0 if ok else 1


def _cmd_rotate(args: argparse.Namespace) -> int:
    raw, record = _store(args).rotate(args.token_id, expires_days=args.expires_days)
    _emit_secret(raw, record)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hb-mcp-auth", description=__doc__)
    parser.add_argument("--store", help="explicit token store path (else env/config default)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create-token", help="mint a token (raw shown once)")
    p_create.add_argument("--client", required=True, choices=sorted(ALLOWED_TOKEN_CLIENTS))
    p_create.add_argument("--label", required=True, help="human client label")
    p_create.add_argument("--actor", required=True, help="actor identity for audit")
    p_create.add_argument("--expires-days", type=int, default=30)
    p_create.add_argument("--tier", default=None, help="informational capability tier")
    p_create.add_argument("--allowed-tool", action="append", help="optional tool allowlist (repeatable)")
    p_create.set_defaults(func=_cmd_create)

    p_list = sub.add_parser("list-tokens", help="list tokens (no raw secrets)")
    p_list.set_defaults(func=_cmd_list)

    p_revoke = sub.add_parser("revoke-token", help="revoke a token by id")
    p_revoke.add_argument("--token-id", required=True)
    p_revoke.set_defaults(func=_cmd_revoke)

    p_rotate = sub.add_parser("rotate-token", help="revoke a token and mint a replacement")
    p_rotate.add_argument("--token-id", required=True)
    p_rotate.add_argument("--expires-days", type=int, default=30)
    p_rotate.set_defaults(func=_cmd_rotate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
