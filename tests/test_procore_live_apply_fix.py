"""Regression tests for the Procore live-apply blockers found during the degradation investigation.

Three layered bugs made the scheduled production live apply produce 0 synced items:
1. `ProcoreSyncCoordinator` defaulted `environment="prod"`, which is not a valid environment
   (`get_environment_config` raised `Unknown environment: prod`) — every project threw before any API call.
2. `get_environment_config("prod")` hard-failed instead of normalizing the common alias.
3. The coordinator built `ProcoreHTTPClient(transport=None)` WITHOUT `live_enabled=True`, so the
   client had no real transport and every endpoint failed `transport_not_injected`.
"""

from __future__ import annotations

import pytest

from hb_assistant.procore.config import get_environment_config
from hb_assistant.procore.sync import ProcoreSyncCoordinator


def test_environment_prod_alias_resolves_to_production() -> None:
    # "prod" must normalize to "production" rather than raising Unknown environment.
    assert get_environment_config("prod") == get_environment_config("production")


def test_coordinator_default_environment_is_production() -> None:
    assert ProcoreSyncCoordinator().environment == "production"


def test_coordinator_normalizes_prod_alias() -> None:
    assert ProcoreSyncCoordinator(environment="prod").environment == "production"


def test_coordinator_enables_real_transport_only_when_gate_armed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Gate OFF (tests/CI default): no real transport — fail-closed, tests inject a mock instead.
    monkeypatch.delenv("HB_PROCORE_LIVE", raising=False)
    client_off = ProcoreSyncCoordinator()._get_client()
    assert client_off.live_enabled is False

    # Gate ON (HB_PROCORE_LIVE=1, as the scheduler arms for the run): real GET-only transport.
    monkeypatch.setenv("HB_PROCORE_LIVE", "1")
    client_on = ProcoreSyncCoordinator()._get_client()
    assert client_on.live_enabled is True
