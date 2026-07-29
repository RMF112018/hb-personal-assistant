"""CLI surface for Apple local MCC capture (no product HB branding)."""

from __future__ import annotations

import argparse
import json
import os

from hb_assistant.apple_mcc.probes.mail_account import (
    DEFAULT_MAIL_ACCOUNT_NAME,
    list_mail_accounts_via_jxa,
    resolve_mail_account,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="apple-mcc", description="Local Apple Mail/Calendar/Contacts capture"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    probe = sub.add_parser("probe", help="Run source probes")
    probe.add_argument("--domain", choices=("mail", "all"), default="mail")
    probe.add_argument("--mail-account", default=DEFAULT_MAIL_ACCOUNT_NAME)
    probe.add_argument("--live", action="store_true")

    dry = sub.add_parser("dry-run", help="Dry-run matrix entry")
    dry.add_argument("--action", default="status")

    cap = sub.add_parser("capture", help="Bounded live capture to spool and NAS staging")
    cap.add_argument("--account", default=DEFAULT_MAIL_ACCOUNT_NAME)
    cap.add_argument("--mailbox", default="Inbox")
    cap.add_argument("--limit", type=int, default=5)
    cap.add_argument("--no-transport", action="store_true")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "dry-run":
        print(json.dumps({"action": args.action, "dry_run": True, "ok": True}))
        return 0
    if args.cmd == "probe":
        if args.live or os.environ.get("APPLE_MCC_LIVE") == "1":
            accounts = list_mail_accounts_via_jxa()
            r = resolve_mail_account(expected_name=args.mail_account, accounts=accounts)
        else:
            r = resolve_mail_account(
                expected_name=args.mail_account,
                accounts=[{"name": args.mail_account, "id": "synthetic"}],
            )
        print(json.dumps(r.to_dict()))
        return 0 if r.ok else 2
    if args.cmd == "capture":
        from hb_assistant.apple_mcc.ops.capture_run import main as capture_main

        argv2 = [
            "--account",
            args.account,
            "--mailbox",
            args.mailbox,
            "--limit",
            str(args.limit),
        ]
        if args.no_transport:
            argv2.append("--no-transport")
        return capture_main(argv2)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
