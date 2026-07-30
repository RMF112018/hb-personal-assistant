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
    probe.add_argument("--domain", choices=("mail", "calendar", "contacts", "all"), default="all")
    probe.add_argument("--mail-account", default=DEFAULT_MAIL_ACCOUNT_NAME)
    probe.add_argument("--live", action="store_true")

    dry = sub.add_parser("dry-run", help="Dry-run matrix entry")
    dry.add_argument("--action", default="status")

    cap = sub.add_parser("capture", help="Bounded live multi-domain capture → NAS staging")
    cap.add_argument("--domains", default="mail,calendar,contacts")
    cap.add_argument("--account", default=DEFAULT_MAIL_ACCOUNT_NAME)
    cap.add_argument("--mailbox", default="Inbox")
    cap.add_argument("--mail-limit", type=int, default=5)
    cap.add_argument("--calendar-days", type=int, default=30)
    cap.add_argument("--calendar-limit", type=int, default=200)
    cap.add_argument("--calendar-sources", default="iCloud")
    cap.add_argument("--contacts-limit", type=int, default=20)
    cap.add_argument("--contacts-containers", default="iCloud,BF-Personal")
    cap.add_argument("--no-transport", action="store_true")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "dry-run":
        print(json.dumps({"action": args.action, "dry_run": True, "ok": True}))
        return 0
    if args.cmd == "probe":
        results = {}
        if args.domain in ("mail", "all"):
            if args.live or os.environ.get("APPLE_MCC_LIVE") == "1":
                accounts = list_mail_accounts_via_jxa()
                r = resolve_mail_account(expected_name=args.mail_account, accounts=accounts)
            else:
                r = resolve_mail_account(
                    expected_name=args.mail_account,
                    accounts=[{"name": args.mail_account, "id": "synthetic"}],
                )
            results["mail"] = r.to_dict()
        if args.domain in ("calendar", "all") and (args.live or os.environ.get("APPLE_MCC_LIVE") == "1"):
            from hb_assistant.apple_mcc.ops.capture_run import export_calendar_live

            try:
                cal = export_calendar_live(days=7, limit=3)
                results["calendar"] = {
                    "state": "ok",
                    "exported_sample": cal.get("exported"),
                    "range": {"start": cal.get("start"), "end": cal.get("end")},
                }
            except Exception as exc:  # noqa: BLE001
                results["calendar"] = {"state": "error", "detail": str(exc)[:300]}
        if args.domain in ("contacts", "all") and (args.live or os.environ.get("APPLE_MCC_LIVE") == "1"):
            from hb_assistant.apple_mcc.ops.capture_run import export_contacts_live

            try:
                cn = export_contacts_live(limit=3, containers="iCloud,BF-Personal")
                results["contacts"] = {
                    "state": "ok",
                    "total": cn.get("total"),
                    "exported_sample": cn.get("exported"),
                }
            except Exception as exc:  # noqa: BLE001
                results["contacts"] = {"state": "error", "detail": str(exc)[:300]}
        print(json.dumps(results, indent=2))
        # mail probe gates exit when mail requested
        if "mail" in results and results["mail"].get("state") != "ok":
            return 2
        return 0
    if args.cmd == "capture":
        from hb_assistant.apple_mcc.ops.capture_run import main as capture_main

        argv2 = [
            "--domains",
            args.domains,
            "--account",
            args.account,
            "--mailbox",
            args.mailbox,
            "--mail-limit",
            str(args.mail_limit),
            "--calendar-days",
            str(args.calendar_days),
            "--calendar-limit",
            str(args.calendar_limit),
            "--calendar-sources",
            args.calendar_sources,
            "--contacts-limit",
            str(args.contacts_limit),
            "--contacts-containers",
            args.contacts_containers,
        ]
        if args.no_transport:
            argv2.append("--no-transport")
        return capture_main(argv2)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
