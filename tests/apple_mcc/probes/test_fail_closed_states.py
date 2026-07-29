"""Fail-closed probe state matrix."""

from __future__ import annotations

from hb_assistant.apple_mcc.probes.mail_account import resolve_mail_account
from hb_assistant.apple_mcc.probes.status import ProbeResult, ProbeState


def test_probe_result_ok_property() -> None:
    assert ProbeResult(domain="x", state=ProbeState.OK).ok
    assert not ProbeResult(domain="x", state=ProbeState.ERROR).ok


def test_mail_error_on_bad_runner() -> None:
    def bad(_argv):  # type: ignore[no-untyped-def]
        raise RuntimeError("boom")

    # Force live path without accounts list
    r = resolve_mail_account(accounts=None, runner=bad)  # type: ignore[arg-type]
    assert r.state is ProbeState.ERROR
