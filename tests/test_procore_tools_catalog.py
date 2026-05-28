"""Phase 04 Prompt 03 — ``hb-assistant procore tools catalog`` CLI tests."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")


def _invoke_catalog(*extra: str) -> dict:
    runner = CliRunner()
    res = runner.invoke(
        app,
        ["procore", "tools", "catalog", "--json", *extra],
        catch_exceptions=False,
    )
    assert res.exit_code == 0, res.output
    return json.loads(res.output)


def test_catalog_envelope_shape_and_counts() -> None:
    payload = _invoke_catalog()
    for key in (
        "command",
        "schema_version",
        "company_id",
        "company_display_name",
        "version",
        "endpoint_count",
        "include_ineligible",
        "summary",
        "endpoints",
        "guardrails",
    ):
        assert key in payload, f"missing top-level key: {key}"
    assert payload["command"] == "hb-assistant procore tools catalog"
    assert payload["endpoint_count"] == 13
    assert payload["include_ineligible"] is True
    summary = payload["summary"]
    assert summary["by_verification_status"] == {
        "official_docs_verified": 10,
        "excluded_by_guardrail": 1,
        "deferred_by_guardrail": 2,
    }
    assert summary["live_eligible_count"] == 10


def test_catalog_each_endpoint_carries_structured_fields() -> None:
    payload = _invoke_catalog()
    required_fields = {
        "endpoint_id",
        "verification_status",
        "official_reference_url",
        "verified_at_utc",
        "verified_by",
        "live_dry_run_receipt_id",
        "verification_reason",
        "is_live_eligible",
    }
    for ep in payload["endpoints"]:
        missing = required_fields - set(ep.keys())
        assert not missing, f"endpoint {ep.get('endpoint_id')!r} missing {missing}"


def test_catalog_filter_to_live_eligible_only() -> None:
    payload = _invoke_catalog("--no-include-ineligible")
    assert payload["include_ineligible"] is False
    assert payload["endpoint_count"] == 10
    for ep in payload["endpoints"]:
        assert ep["is_live_eligible"] is True
        assert ep["verification_status"] == "official_docs_verified"
        assert ep["status"] in ("validated", "sensitive_validated")
