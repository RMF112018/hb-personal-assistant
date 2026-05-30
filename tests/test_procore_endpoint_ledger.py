"""Tests for the Phase 06B Prompt 01 endpoint promotion ledger.

Pure derivation over the canonical registry + the `procore live endpoints ledger`
CLI surface. No HTTP, no live Procore, no vault writes.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.procore import endpoints as ep_registry
from hb_assistant.procore.endpoint_ledger import build_promotion_ledger

# The three endpoints that must remain explicitly fail-closed (held) until an
# operator runs a bounded live smoke / resolves the path + permission grant.
_HELD_ENDPOINTS = {
    "purchase-order-detail-line-items",
    "budget-change-line-items",
    "budget-details",
}


def test_ledger_row_count_equals_registry_count() -> None:
    payload = build_promotion_ledger()
    registry_count = len(ep_registry.list_all())
    assert payload["registry_endpoint_count"] == registry_count
    assert payload["ledger_row_count"] == registry_count
    assert len(payload["ledger"]) == registry_count


def test_promoted_and_held_partition() -> None:
    payload = build_promotion_ledger()
    assert payload["promoted_count"] == 56
    assert payload["held_count"] == 3
    assert payload["promoted_count"] + payload["held_count"] == payload["ledger_row_count"]


def test_held_endpoints_retain_fail_closed_status() -> None:
    payload = build_promotion_ledger()
    held = {r["endpoint_id"] for r in payload["ledger"] if r["promotion_status"] == "held"}
    assert held == _HELD_ENDPOINTS
    for row in payload["ledger"]:
        if row["endpoint_id"] in _HELD_ENDPOINTS:
            assert row["promotion_status"] == "held"
            assert row["live_verified"] is False
            assert row["last_verified_date"] is None
            assert "fail-closed" in row["next_step"]


def test_every_row_has_required_fields() -> None:
    required = {
        "endpoint_id",
        "family",
        "live_verified",
        "promotion_status",
        "verification_reason",
        "evidence_path",
        "last_verified_date",
        "next_step",
    }
    for row in build_promotion_ledger()["ledger"]:
        assert required <= set(row.keys())
        assert row["promotion_status"] in ("promoted", "held")
        assert row["evidence_path"].startswith("docs/evidence/")


def test_promoted_rows_carry_verified_date() -> None:
    for row in build_promotion_ledger()["ledger"]:
        if row["promotion_status"] == "promoted":
            assert row["last_verified_date"] is not None
            assert row["next_step"] == "none — live-verified; monitor for drift"


def test_cli_ledger_emits_matching_counts() -> None:
    runner = CliRunner()
    res = runner.invoke(app, ["procore", "live", "endpoints", "ledger", "--json"], catch_exceptions=False)
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["command"] == "hb-assistant procore live endpoints ledger"
    assert payload["ledger_row_count"] == len(ep_registry.list_all())
    assert payload["held_count"] == 3
    assert payload["guardrails"]["writeback"] == "none"
    assert payload["guardrails"]["live_calls_disabled"] is True
