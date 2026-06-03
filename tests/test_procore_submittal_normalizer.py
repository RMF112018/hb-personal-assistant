"""Phase 04 Prompt 05 — Submittal canonical normalization (pure-function unit tests)."""

from __future__ import annotations

import json

from hb_assistant.construction.fixtures.procore import SUBMITTAL_SAMPLE_PAYLOAD
from hb_assistant.procore.normalizers.submittal import (
    NORMALIZATION_SCHEMA_VERSION,
    normalize_submittal,
    normalize_submittal_package,
    normalize_submittal_payload_block,
    normalize_submittal_response,
)

_FETCHED_AT = "2026-05-28T00:00:00+00:00"
_CORRELATION = "synthetic-corr-002"


def test_normalize_submittal_carries_canonical_keys_and_metadata() -> None:
    raw = SUBMITTAL_SAMPLE_PAYLOAD[0]
    record = normalize_submittal(
        raw,
        project_key="tropical",
        endpoint_id="list-submittals",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["source_project_key"] == "tropical"
    assert record["endpoint_id"] == "list-submittals"
    assert record["category"] == "submittals"
    assert record["entity_stable_key"] == raw["id"]
    assert record["correlation_id"] == _CORRELATION
    assert record["redaction_applied"] is True
    assert record["normalization_schema_version"] == NORMALIZATION_SCHEMA_VERSION
    fields = record["canonical_fields"]
    assert fields["number"] == raw["number"]
    assert fields["title"] == raw["title"]
    assert fields["status"] == raw["status"]
    assert fields["type"] == raw["type"]
    assert fields["specification_section"] == raw["specification_section"]
    assert fields["source_url"] == raw["html_url"]


def test_normalize_submittal_review_flag_low_risk_default() -> None:
    raw = SUBMITTAL_SAMPLE_PAYLOAD[0]
    record = normalize_submittal(
        raw,
        project_key="tropical",
        endpoint_id="list-submittals",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is False
    assert record["routing_reason"] == "default_low_risk"


def test_normalize_submittal_review_flag_revise_and_resubmit_status() -> None:
    raw = SUBMITTAL_SAMPLE_PAYLOAD[2]  # status: revise_and_resubmit, contract amendment subject, no assignee
    record = normalize_submittal(
        raw,
        project_key="tropical",
        endpoint_id="list-submittals",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is True
    # Status fragment fires before subject + assignee fragments
    assert record["routing_reason"].startswith("status_contains:")


def test_normalize_submittal_review_flag_assignee_missing() -> None:
    record = normalize_submittal(
        {"id": "x1", "status": "open", "title": "Generic submittal"},
        project_key="tropical",
        endpoint_id="list-submittals",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is True
    assert record["routing_reason"] == "assignee_missing"


def test_normalize_submittal_source_url_synthesized_from_html_url() -> None:
    record = normalize_submittal(
        {
            "id": "x2",
            "html_url": "https://example.com/submittals/x2",
            "assignee_id": "u1",
        },
        project_key="tropical",
        endpoint_id="list-submittals",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["canonical_fields"]["source_url"] == "https://example.com/submittals/x2"


def test_normalize_submittal_captures_full_response_shape_with_redaction() -> None:
    raw = {
        "id": "55321441",
        "actual_delivery_date": "2022-08-19",
        "bic_due_date": "2022-08-19",
        "confirmed_delivery_date": "2022-08-19",
        "closed_at": "2022-08-19T17:00:00Z",
        "cost_code_id": "cost-1",
        "current_step_approvers": [
            {
                "id": "12345",
                "response_required": True,
                "user": {"id": "67890", "name": "Sensitive Person"},
            }
        ],
        "current_step_returned_date": "2022-08-19",
        "current_step_sent_date": "2022-08-19",
        "custom_textarea_1": "textarea body must not persist",
        "custom_textfield_1": "textfield body must not persist",
        "description": "description body must not persist",
        "design_team_review_time": 42,
        "distribution_member_ids": [42],
        "due_date": "2022-08-19",
        "internal_review_time": 42,
        "issue_date": "2022-08-19",
        "lead_time": 42,
        "location_id": "loc-1",
        "number": "S-001",
        "private": True,
        "received_date": "2022-08-19",
        "received_from_id": "received-1",
        "required_on_site_date": "2022-08-19",
        "responsible_contractor_id": "company-1",
        "revision": "0",
        "scheduled_task_key": "task-key",
        "scheduled_task_id": "task-id",
        "specification_section_id": "spec-1",
        "status_id": "status-1",
        "sub_job_id": "subjob-1",
        "submit_by": "2022-08-19",
        "submittal_manager_id": "manager-1",
        "submittal_package_id": "package-1",
        "title": "Submittal Title",
        "type": "Shop Drawing",
        "workflow_step": {"current_step": 1, "total_steps": 3, "days_late": 2},
        "custom_field_string_definition": {
            "data_type": "string",
            "value": "custom field body must not persist",
        },
        "custom_field_decimal_definition": {"data_type": "decimal", "value": 2.2},
        "custom_field_boolean_definition": {"data_type": "boolean", "value": True},
        "custom_field_lov_entry_definition": {
            "data_type": "lov_entry",
            "value": {"id": "1", "label": "Open"},
        },
        "custom_field_lov_entries_definition": {
            "data_type": "lov_entries",
            "value": [{"id": "2", "label": "Open"}],
        },
    }

    record = normalize_submittal(
        raw,
        project_key="tropical",
        endpoint_id="submittals",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )

    fields = record["canonical_fields"]
    expected_keys = {
        "id",
        "actual_delivery_date",
        "bic_due_date",
        "confirmed_delivery_date",
        "closed_at",
        "cost_code_id",
        "current_step_approvers",
        "current_step_returned_date",
        "current_step_sent_date",
        "custom_textarea_1",
        "custom_textfield_1",
        "description",
        "design_team_review_time",
        "distribution_member_ids",
        "due_date",
        "internal_review_time",
        "issue_date",
        "lead_time",
        "location_id",
        "number",
        "private",
        "received_date",
        "received_from_id",
        "required_on_site_date",
        "responsible_contractor_id",
        "revision",
        "scheduled_task_key",
        "scheduled_task_id",
        "specification_section_id",
        "status_id",
        "sub_job_id",
        "submit_by",
        "submittal_manager_id",
        "submittal_package_id",
        "title",
        "type",
        "workflow_step",
        "custom_field_string_definition",
        "custom_field_decimal_definition",
        "custom_field_boolean_definition",
        "custom_field_lov_entry_definition",
        "custom_field_lov_entries_definition",
    }
    assert expected_keys <= set(fields)
    assert fields["workflow_step"] == {"current_step": 1, "total_steps": 3, "days_late": 2}
    assert fields["distribution_member_ids"] == [42]
    assert fields["current_step_approvers"][0]["user"]["id"] == "67890"
    assert "name_hash_prefix" in fields["current_step_approvers"][0]["user"]
    assert fields["custom_field_decimal_definition"]["value"] == 2.2
    assert fields["custom_field_boolean_definition"]["value"] is True
    assert fields["custom_field_lov_entry_definition"]["value"] == {"id": "1", "label": "Open"}
    assert fields["custom_field_lov_entries_definition"]["value"] == [{"id": "2", "label": "Open"}]
    assert fields["description"]["hash_prefix"]
    assert fields["custom_textarea_1"]["hash_prefix"]
    assert fields["custom_textfield_1"]["hash_prefix"]
    assert fields["custom_field_string_definition"]["value_summary"]["hash_prefix"]

    serialized = json.dumps(record)
    for forbidden in (
        "Sensitive Person",
        "textarea body must not persist",
        "textfield body must not persist",
        "description body must not persist",
        "custom field body must not persist",
    ):
        assert forbidden not in serialized


def test_normalize_submittal_response_always_review_required() -> None:
    raw_response = SUBMITTAL_SAMPLE_PAYLOAD[0]["responses"][0]
    record = normalize_submittal_response(
        raw_response,
        parent_procore_id="synthetic-sub-001",
        project_key="tropical",
        endpoint_id="list-submittals",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is True
    assert record["routing_reason"] == "submittal_response_default_review_required"
    assert record["category"] == "submittal_responses"
    assert record["parent_submittal_stable_key"] == "synthetic-sub-001"
    assert record["entity_stable_key"].startswith("response-synthetic-sub-001-")
    # Comment body reduced to hash-only summary — never the text itself.
    serialized = json.dumps(record)
    assert raw_response["comment"] not in serialized


def test_normalize_submittal_package_always_review_required() -> None:
    raw_package = SUBMITTAL_SAMPLE_PAYLOAD[0]["packages"][0]
    record = normalize_submittal_package(
        raw_package,
        parent_procore_id="synthetic-sub-001",
        project_key="tropical",
        endpoint_id="list-submittals",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert record["review_required"] is True
    assert record["routing_reason"] == "submittal_package_default_review_required"
    assert record["category"] == "submittal_packages"
    assert record["entity_stable_key"].startswith("package-synthetic-sub-001-")
    fields = record["canonical_fields"]
    assert fields["number"] == raw_package["number"]
    assert fields["title"] == raw_package["title"]


def test_normalize_submittal_payload_block_yields_three_lists() -> None:
    submittals, responses, packages = normalize_submittal_payload_block(
        SUBMITTAL_SAMPLE_PAYLOAD,
        project_key="tropical",
        endpoint_id="list-submittals",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    assert len(submittals) == 3
    assert len(responses) == 4
    assert len(packages) == 2
    response_parents = {r["parent_submittal_stable_key"] for r in responses}
    package_parents = {p["parent_submittal_stable_key"] for p in packages}
    assert response_parents == {
        "synthetic-sub-001",
        "synthetic-sub-002",
        "synthetic-sub-003",
    }
    assert package_parents == {"synthetic-sub-001", "synthetic-sub-003"}


def test_normalize_submittal_payload_block_never_serializes_body_text() -> None:
    submittals, responses, packages = normalize_submittal_payload_block(
        SUBMITTAL_SAMPLE_PAYLOAD,
        project_key="tropical",
        endpoint_id="list-submittals",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    serialized = json.dumps(
        {"submittals": submittals, "responses": responses, "packages": packages}
    )
    for raw in SUBMITTAL_SAMPLE_PAYLOAD:
        for raw_response in raw["responses"]:
            assert raw_response["comment"] not in serialized
        for raw_package in raw["packages"]:
            description = raw_package.get("description")
            if description:
                assert description not in serialized
