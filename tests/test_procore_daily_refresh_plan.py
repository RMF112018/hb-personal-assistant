"""Unit tests for the canonical daily-refresh plan + status taxonomy.

Pure, network-free, DB-free coverage of procore/daily_refresh_plan.py:
the endpoint plan (scope classification, alias mapping, date-windowing,
unsupported drawings), the bounded daily-log window, and the receipt->taxonomy
classifier for HTTP 400/403/404/429/5xx and gate/verify states.
"""

from __future__ import annotations

from datetime import date

from hb_assistant.procore import daily_refresh_plan as drp

# --- plan structure ---------------------------------------------------------------


def test_plan_maps_legacy_aliases_to_canonical_ids() -> None:
    plan = drp.build_daily_refresh_plan()
    by_alias = {pe.legacy_alias: pe.canonical_id for pe in plan}
    assert by_alias["list-projects"] == "projects"
    assert by_alias["list-change-events"] == "change-events"
    assert by_alias["list-invoices"] == "subcontractor-invoices"
    assert by_alias["list-punch-items"] == "punch-items"
    assert by_alias["list-prime-contracts"] == "prime-contracts"
    assert by_alias["list-rfis"] == "rfis"
    assert by_alias["list-submittals"] == "submittals"
    assert by_alias["list-commitments"] == "commitment-contracts"


def test_only_projects_is_company_level() -> None:
    plan = drp.build_daily_refresh_plan()
    company = [pe.canonical_id for pe in plan if pe.company_level]
    assert company == ["projects"]


def test_daily_log_endpoints_are_date_windowed_and_present() -> None:
    plan = drp.build_daily_refresh_plan()
    dl = [pe for pe in plan if pe.legacy_alias == "list-daily-logs"]
    assert dl, "daily-log family must be in the plan"
    assert all(pe.date_windowed for pe in dl)
    assert all(pe.canonical_id.startswith("daily-log-") for pe in dl)
    # non-daily-log endpoints are not date-windowed
    assert all(not pe.date_windowed for pe in plan if pe.legacy_alias != "list-daily-logs")


def test_drawings_is_unsupported_not_in_plan() -> None:
    plan = drp.build_daily_refresh_plan()
    assert all(pe.legacy_alias != "list-drawings" for pe in plan)
    assert drp.UNSUPPORTED_ENDPOINTS["list-drawings"] == "skipped_tool_not_enabled"


def test_daily_log_window_is_bounded() -> None:
    start, end = drp.daily_log_window(date(2026, 6, 9), lookback_days=7)
    assert end == "2026-06-09"
    assert start == "2026-06-02"


# --- taxonomy classification ------------------------------------------------------


def test_success_state() -> None:
    assert drp.classify_receipt({"state": "success"}) == "success"


def test_partial_success_without_projection_error_is_success() -> None:
    assert drp.classify_receipt({"state": "partial_success", "redacted_errors": []}) == "success"


def test_partial_success_with_projection_error() -> None:
    receipt = {
        "state": "partial_success",
        "redacted_errors": [{"inspection_projection_error": "projection_failed"}],
    }
    assert drp.classify_receipt(receipt) == "projection_error"


def test_http_400_is_contract_bug() -> None:
    receipt = {
        "state": "transport_error",
        "reason_codes": ["transport_error:400"],
        "redacted_errors": [{"code": "http_error", "status": 400}],
    }
    assert drp.classify_receipt(receipt) == "contract_bug_missing_required_param"


def test_http_403_is_permission_limited() -> None:
    receipt = {"state": "transport_error", "redacted_errors": [{"status": 403}]}
    assert drp.classify_receipt(receipt) == "skipped_permission_limited"


def test_http_404_is_tool_not_enabled() -> None:
    receipt = {"state": "transport_error", "redacted_errors": [{"status": 404}]}
    assert drp.classify_receipt(receipt) == "skipped_tool_not_enabled"


def test_http_429_is_rate_limited() -> None:
    receipt = {
        "state": "transport_error",
        "reason_codes": ["transport_error:429_rate_limited"],
        "redacted_errors": [{"status": 429}],
    }
    assert drp.classify_receipt(receipt) == "transport_rate_limited"


def test_http_5xx_is_retryable() -> None:
    receipt = {"state": "transport_error", "redacted_errors": [{"status": 503}]}
    assert drp.classify_receipt(receipt) == "transport_error_retryable"


def test_transport_error_without_status_is_non_retryable() -> None:
    receipt = {"state": "transport_error", "redacted_errors": [{"orchestrator_error": "Boom"}]}
    assert drp.classify_receipt(receipt) == "transport_error_non_retryable"


def test_gate_blocked_auth() -> None:
    receipt = {"state": "gate_blocked", "reason_codes": ["live_env_not_set"]}
    assert drp.classify_receipt(receipt) == "blocked_auth_not_ready"


def test_gate_blocked_mapping() -> None:
    receipt = {"state": "gate_blocked", "reason_codes": ["mapping_not_live_eligible"]}
    assert drp.classify_receipt(receipt) == "blocked_mapping_not_ready"


def test_not_live_verified_is_skipped() -> None:
    assert drp.classify_receipt({"state": "not_live_verified"}) == "skipped_not_live_eligible"


def test_fail_closed_unsupported_normalizer_missing() -> None:
    receipt = {"state": "fail_closed_unsupported", "reason_codes": ["normalizer_missing"]}
    assert drp.classify_receipt(receipt) == "normalizer_missing"


def test_fail_closed_unsupported_default_is_tool_not_enabled() -> None:
    receipt = {"state": "fail_closed_unsupported", "reason_codes": ["endpoint_alias_unknown"]}
    assert drp.classify_receipt(receipt) == "skipped_tool_not_enabled"


# --- degradation semantics --------------------------------------------------------


def test_contract_bug_is_degradation() -> None:
    assert drp.is_degraded_status("contract_bug_missing_required_param") is True
    assert drp.is_degraded_status("transport_rate_limited") is True
    assert drp.is_degraded_status("projection_error") is True


def test_skips_are_not_degradation() -> None:
    assert drp.is_degraded_status("skipped_tool_not_enabled") is False
    assert drp.is_degraded_status("skipped_company_level_already_handled") is False
    assert drp.is_degraded_status("success") is False
    assert drp.is_skipped_status("skipped_permission_limited") is True
    assert drp.is_skipped_status("success") is False
