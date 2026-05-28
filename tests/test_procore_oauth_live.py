"""Live Procore OAuth refresh test (skipped by default).

Runs only when both ``HB_PROCORE_LIVE=1`` and ``PROCORE_TEST_REFRESH_TOKEN``
are set in the environment. The test exchanges the supplied refresh token
against real Procore and asserts a non-empty access token is returned. The
token value is **immediately discarded** — never printed, never written to
the local cache, never echoed.

Operator-only. Not part of CI. Documented in the Phase 04 Prompt 02
acquisition-remediation evidence.
"""

from __future__ import annotations

import os

import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.environ.get("HB_PROCORE_LIVE"),
        reason="HB_PROCORE_LIVE=1 required for live Procore OAuth tests",
    ),
    pytest.mark.skipif(
        not os.environ.get("PROCORE_TEST_REFRESH_TOKEN"),
        reason="PROCORE_TEST_REFRESH_TOKEN required for live refresh test",
    ),
]


def test_live_refresh_returns_access_token() -> None:
    from hb_assistant.procore.oauth import ProcoreOAuthClient

    refresh_token = os.environ["PROCORE_TEST_REFRESH_TOKEN"]
    client = ProcoreOAuthClient(environment="production")
    token_set = client.refresh_access_token(refresh_token)
    assert token_set.access_token, "refresh did not return an access token"
    # Discard immediately. Never assert on the value, never echo it.
    del token_set
