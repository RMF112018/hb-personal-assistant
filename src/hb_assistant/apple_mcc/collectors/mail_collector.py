"""Mail collector (read-only; no private DB writes)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hb_assistant.apple_mcc.probes.mail_account import (
    DEFAULT_MAIL_ACCOUNT_NAME,
    resolve_mail_account,
)


@dataclass
class MailCollectPlan:
    account_name: str
    mailbox: str
    limit: int


def plan_collect(*, account_name: str = DEFAULT_MAIL_ACCOUNT_NAME, mailbox: str = "INBOX", limit: int = 50) -> MailCollectPlan:
    r = resolve_mail_account(accounts=[{"name": account_name, "id": "x"}])
    if not r.ok:
        raise RuntimeError(f"mail_account_not_resolved:{r.state.value}")
    return MailCollectPlan(account_name=account_name, mailbox=mailbox, limit=limit)


def collect_from_fixtures(fixture_dir: Path) -> list[bytes]:
    return [p.read_bytes() for p in sorted(fixture_dir.glob("*.eml"))]
