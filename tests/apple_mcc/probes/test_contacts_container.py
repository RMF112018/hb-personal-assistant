"""Contacts container probe tests."""

from __future__ import annotations

from hb_assistant.apple_mcc.probes.contacts_container import resolve_contacts_containers
from hb_assistant.apple_mcc.probes.status import ProbeState


def test_contacts_containers_allowlist() -> None:
    r = resolve_contacts_containers(
        containers=[{"name": "iCloud"}, {"name": "OtherApp"}]
    )
    assert r.state is ProbeState.OK
    assert "iCloud" in (r.selected or "")


def test_contacts_disabled() -> None:
    r = resolve_contacts_containers(containers=[{"name": "iCloud"}], enabled=False)
    assert r.state is ProbeState.DISABLED


def test_contacts_missing() -> None:
    r = resolve_contacts_containers(containers=[{"name": "Weird"}])
    assert r.state is ProbeState.MISSING
