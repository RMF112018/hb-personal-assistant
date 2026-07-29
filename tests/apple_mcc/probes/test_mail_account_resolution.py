"""Mail account resolution probes (BF-Personal exact name)."""

from __future__ import annotations

from hb_assistant.apple_mcc.probes.mail_account import (
    DEFAULT_MAIL_ACCOUNT_NAME,
    resolve_mail_account,
)
from hb_assistant.apple_mcc.probes.status import ProbeState


def test_default_locator_is_bf_personal() -> None:
    assert DEFAULT_MAIL_ACCOUNT_NAME == "BF-Personal"


def test_exact_one_mail_account_named_bf_personal() -> None:
    accounts = [
        {"name": "Work", "id": "1"},
        {"name": "BF-Personal", "id": "2"},
        {"name": "Other", "id": "3"},
    ]
    r = resolve_mail_account(accounts=accounts)
    assert r.state is ProbeState.OK
    assert r.selected == "BF-Personal"
    assert r.ok


def test_missing_bf_personal_fail_closed() -> None:
    r = resolve_mail_account(accounts=[{"name": "HB", "id": "1"}, {"name": "Work", "id": "2"}])
    assert r.state is ProbeState.MISSING
    assert not r.ok
    # Must not fall back to HB
    assert r.selected is None


def test_case_sensitive_no_match() -> None:
    r = resolve_mail_account(accounts=[{"name": "bf-personal", "id": "1"}])
    assert r.state is ProbeState.MISSING


def test_ambiguous_duplicate_names() -> None:
    r = resolve_mail_account(
        accounts=[{"name": "BF-Personal", "id": "1"}, {"name": "BF-Personal", "id": "2"}]
    )
    assert r.state is ProbeState.AMBIGUOUS
