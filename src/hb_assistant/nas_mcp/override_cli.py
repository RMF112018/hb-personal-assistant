"""Operator CLI for NAS MCP temporary limit overrides (create / list / revoke).

Standalone argparse tool (does NOT import the full Typer app / forbidden FastAPI backend).
Local/operator-only by design — this is the ONLY way to create an override; no MCP tool can,
so a remote LLM can never self-approve one. Every override is narrow, reason-required, and
auto-expiring. Run::

    python -m hb_assistant.nas_mcp.override_cli create --client claude \\
        --scope search_results --max-value 100 --expires-minutes 30 --reason "triage sweep"
    python -m hb_assistant.nas_mcp.override_cli list
    python -m hb_assistant.nas_mcp.override_cli revoke --override-id <id>

Creation also writes an audit receipt to the NAS MCP audit log.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .audit import NasMcpAuditWriter
from .config import NasMcpConfig
from .overrides import KNOWN_SCOPES, OverrideStore


def _config() -> NasMcpConfig:
    return NasMcpConfig.from_env()


def _store(args: argparse.Namespace) -> OverrideStore:
    if args.store:
        return OverrideStore(Path(args.store))
    cfg = _config()
    if not cfg.override_store_path:
        raise SystemExit("override store path unresolved; set HB_MCP_OVERRIDE_STORE")
    return OverrideStore(Path(cfg.override_store_path))


def _cmd_create(args: argparse.Namespace) -> int:
    record = _store(args).create(
        scope=args.scope,
        max_value=args.max_value,
        client_label=args.client,
        expires_minutes=args.expires_minutes,
        reason=args.reason,
        created_by=args.created_by,
        tool_name=args.tool,
    )
    # Audit the creation (operator action) — no secret material in an override record.
    if not args.store:  # only when using the real configured store
        cfg = _config()
        NasMcpAuditWriter(cfg.audit_dir).write(
            {
                "surface": "override_cli",
                "decision": "allow",
                "operation": "override_create",
                "override_id": record["override_id"],
                "scope": record["scope"],
                "client_label": record["client_label"],
                "reason": record["reason"],
                "expires_at": record["expires_at"],
                "audit_receipt_id": record["audit_receipt_id"],
                "write_attempted": False,
            }
        )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    print(json.dumps(_store(args).list_overrides(), indent=2, sort_keys=True))
    return 0


def _cmd_revoke(args: argparse.Namespace) -> int:
    ok = _store(args).revoke(args.override_id)
    print(json.dumps({"override_id": args.override_id, "revoked": ok}))
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hb-mcp-override", description=__doc__)
    parser.add_argument("--store", help="explicit override store path (else config default)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="create a narrow, expiring override")
    p_create.add_argument("--scope", required=True, choices=sorted(KNOWN_SCOPES))
    p_create.add_argument("--max-value", type=int, required=True, help="raised limit value")
    p_create.add_argument("--client", default="any", help="client label to scope to (default: any)")
    p_create.add_argument("--tool", default=None, help="tool name (required for scope 'specific_tool')")
    p_create.add_argument("--expires-minutes", type=int, required=True)
    p_create.add_argument("--reason", required=True)
    p_create.add_argument("--created-by", default="operator")
    p_create.set_defaults(func=_cmd_create)

    p_list = sub.add_parser("list", help="list overrides")
    p_list.set_defaults(func=_cmd_list)

    p_revoke = sub.add_parser("revoke", help="revoke an override by id")
    p_revoke.add_argument("--override-id", required=True)
    p_revoke.set_defaults(func=_cmd_revoke)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
