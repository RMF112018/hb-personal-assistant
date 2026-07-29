"""CLI surface for Apple local MCC capture (no product HB branding)."""

from __future__ import annotations

import argparse
import json

from hb_assistant.apple_mcc.probes.mail_account import (
    DEFAULT_MAIL_ACCOUNT_NAME,
    resolve_mail_account,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="apple-mcc", description="Local Apple Mail/Calendar/Contacts capture")
    sub = p.add_subparsers(dest="cmd", required=True)
    probe = sub.add_parser("probe", help="Run source probes")
    probe.add_argument("--domain", choices=("mail", "all"), default="mail")
    probe.add_argument("--mail-account", default=DEFAULT_MAIL_ACCOUNT_NAME)
    dry = sub.add_parser("dry-run", help="Dry-run matrix entry")
    dry.add_argument("--action", default="status")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "dry-run":
        print(json.dumps({"action": args.action, "dry_run": True, "ok": True}))
        return 0
    if args.cmd == "probe":
        # Synthetic accounts path is for CI; live JXA used when APPLE_MCC_LIVE=1
        import os

        if os.environ.get("APPLE_MCC_LIVE") == "1":
            r = resolve_mail_account(expected_name=args.mail_account)
        else:
            r = resolve_mail_account(
                expected_name=args.mail_account,
                accounts=[{"name": args.mail_account, "id": "synthetic"}],
            )
        print(json.dumps(r.to_dict()))
        return 0 if r.ok else 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
