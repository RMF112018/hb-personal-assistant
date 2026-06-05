"""Phase 04B daily-log live normalizers — real field contracts + entity
projection + PII-safety. Fixtures mirror the operator-supplied Procore
response shapes with clearly synthetic values; every PII value below must be
absent (hashed) from the normalized output.
"""

from __future__ import annotations

import json

import pytest

from hb_assistant.procore.normalizers import daily_log_live as dll

_KW = {
    "project_key": "tropical",
    "correlation_id": "synthetic-corr",
    "fetched_at": "2026-05-29T00:00:00Z",
}

# A synthetic person object shaped like Procore's created_by / user.
_PERSON = {"id": 160586, "login": "synthetic-carl@example.test", "name": "Synthetic Carl"}
# Synthetic free-text + PII strings that MUST NOT survive normalization.
_PII_STRINGS = [
    "synthetic-carl@example.test",
    "Synthetic Carl",
    "synthetic-contact@example.test",
    "(503) 555-0100",
    "Synthetic Inspector",
    "Synthetic Visitor (Glass Co.)",
    "Synthetic Involved Person",
]
_FREETEXT_STRINGS = [
    "synthetic comment body that must be hashed",
    "synthetic note body that must be hashed",
    "synthetic details body that must be hashed",
    "synthetic safety notice that must be hashed",
]

_LOCATION = {
    "id": 15504,
    "name": "North Building>First Floor",
    "node_name": "Closet",
    "parent_id": 788866,
}
_VENDOR = {"id": 161072, "name": "Synthetic Architecture"}
_SEGMENT = {
    "id": 123456,
    "name": "Morning Shift",
    "description": "synthetic segment description text",
    "deleted": False,
}
_ATTACH = [
    {
        "id": 42,
        "name": "string",
        "filename": "synthetic-file.jpg",
        "content_type": "image/jpeg",
        "url": "https://example.test/rest/v1.0/local_files/abc123?company_id=15&prostore_file_id=76094",
        "share_url": "https://example.test/rest/v1.0/local_files/abc?company_id=15",
        "viewable_url": "https://example.test/15/project/daily_log/show?holder_id=13&prostore_file_id=76094",
    }
]
_CUSTOM_FIELDS = {
    "custom_field_111": {"data_type": "string", "value": "synthetic secret custom value"},
    "custom_field_222": {"data_type": "decimal", "value": 2.2},
    "custom_field_333": {"data_type": "boolean", "value": True},
    "custom_field_444": {"data_type": "lov_entry", "value": {"id": 1, "label": "Open"}},
}


def _norm(fn, endpoint_id, raw):
    return fn(raw, endpoint_id=endpoint_id, **_KW)


def _assert_no_pii_leak(record):
    blob = json.dumps(record)
    for needle in (
        _PII_STRINGS
        + _FREETEXT_STRINGS
        + ["synthetic secret custom value", "synthetic segment description"]
    ):
        assert needle not in blob, f"PII/free-text leaked: {needle!r}"
    # URLs must be path-only — no scheme, no query strings, no signed-url params.
    assert "https://" not in blob
    assert "?" not in blob
    assert "company_id" not in blob and "prostore_file_id" not in blob


# --------------------------------------------------------------------------- #
# weather (path moved to v1.1 /daily_logs/weather_logs)
# --------------------------------------------------------------------------- #


def test_weather_scalars_signals_and_no_leak():
    raw = {
        "id": 20160101,
        "date": "2016-05-19",
        "datetime": "2016-05-19T12:00:00Z",
        "average": 50,
        "sky": "Clear",
        "ground": "Dry",
        "wind": "Calm",
        "temperature": "Hot",
        "precipitation": True,
        "is_weather_delay": 1,
        "calamity": "Fire",
        "comments": _FREETEXT_STRINGS[0],
        "created_by": _PERSON,
        "vendor": _VENDOR,
        "location": _LOCATION,
        "daily_log_segment": _SEGMENT,
        "attachments": _ATTACH,
        "updated_at": "2012-10-24T21:39:40Z",
    }
    rec = _norm(dll.normalize_daily_log_weather, "daily-log-weather", raw)
    cf = rec["canonical_fields"]
    assert rec["review_required"] is False
    assert rec["category"] == "daily_log_weather"
    assert cf["sky"] == "Clear" and cf["temperature"] == "Hot" and cf["calamity"] == "Fire"
    assert "comments_summary" in cf and cf["comments_summary"]["type"] == "string"
    assert "weather_delay" in cf["action_signals"]
    # attachment redaction: path-only.
    att = cf["entities"]["attachments"]["items"][0]
    assert att["url_path"] == "/rest/v1.0/local_files/abc123"
    assert "url" not in att
    _assert_no_pii_leak(rec)


# --------------------------------------------------------------------------- #
# manpower — created_by + user + contact PII; custom_fields typed
# --------------------------------------------------------------------------- #


def test_manpower_hashes_all_people_and_types_custom_fields():
    raw = {
        "id": 333675,
        "date": "2016-05-19",
        "man_hours": "32.0",
        "num_workers": 4,
        "num_hours": "8.0",
        "status": "pending",
        "notes": _FREETEXT_STRINGS[1],
        "vendor": _VENDOR,
        "cost_code": {"id": 12345, "name": "Earthwork"},
        "trade": {"id": 999, "name": "09 - acoustical panels"},
        "user": {"id": 324, "login": "synthetic-contact@example.test", "name": "Synthetic Carl"},
        "contact": {
            "id": 1128828,
            "email": "synthetic-contact@example.test",
            "mobile_phone": "(503) 555-0100",
            "name": "Synthetic Carl",
            "job_title": "Engineer",
        },
        "created_by": _PERSON,
        "location": _LOCATION,
        "attachments": _ATTACH,
        "custom_fields": _CUSTOM_FIELDS,
        "permissions": {"can_update": True, "can_delete": False},
        "updated_at": "2012-10-24T21:39:40Z",
    }
    rec = _norm(dll.normalize_daily_log_manpower, "daily-log-manpower", raw)
    cf = rec["canonical_fields"]
    roles = {p["role"] for p in cf["entities"]["people"]}
    assert {"created_by", "user", "contact"} <= roles
    assert cf["permissions"] == {"can_update": True, "can_delete": False}
    fields = cf["entities"]["custom_fields"]["fields"]
    assert "value_summary" in fields["custom_field_111"]  # string hashed
    assert fields["custom_field_222"]["value"] == 2.2  # decimal preserved
    assert fields["custom_field_333"]["value"] is True  # boolean preserved
    assert fields["custom_field_444"]["value"] == {"id": 1, "label": "Open"}
    _assert_no_pii_leak(rec)


# --------------------------------------------------------------------------- #
# notes — review_required + comment hashed + issue_day signal
# --------------------------------------------------------------------------- #


def test_notes_review_required_and_comment_hashed():
    raw = {
        "id": 333675,
        "comment": _FREETEXT_STRINGS[0],
        "date": "2016-05-19",
        "daily_log_header_id": 151335,
        "is_issue_day": True,
        "status": "pending",
        "created_by": _PERSON,
        "created_by_collaborator": True,
        "vendor": _VENDOR,
        "location": _LOCATION,
        "daily_log_segment": _SEGMENT,
        "attachments": _ATTACH,
        "updated_at": "2012-10-24T21:39:40Z",
    }
    rec = _norm(dll.normalize_daily_log_notes, "daily-log-notes", raw)
    cf = rec["canonical_fields"]
    assert rec["review_required"] is True
    assert "comment_summary" in cf and "comment" not in cf
    assert "issue_day" in cf["action_signals"]
    assert "daily_note_review_required" in cf["action_signals"]
    _assert_no_pii_leak(rec)


def test_manpower_anomaly_signal_when_workers_without_hours():
    anomalous = _norm(
        dll.normalize_daily_log_manpower,
        "daily-log-manpower",
        {"id": 1, "date": "2026-03-15", "num_workers": 6, "man_hours": 0},
    )
    assert "daily_manpower_anomaly" in anomalous["canonical_fields"]["action_signals"]
    balanced = _norm(
        dll.normalize_daily_log_manpower,
        "daily-log-manpower",
        {"id": 2, "date": "2026-03-15", "num_workers": 6, "man_hours": "48.0"},
    )
    assert "daily_manpower_anomaly" not in balanced["canonical_fields"]["action_signals"]


def test_delay_reported_signal():
    rec = _norm(
        dll.normalize_daily_log_delay,
        "daily-log-delays-review-routed",
        {"id": 1, "delay_type": "weather", "duration": 5},
    )
    assert "daily_delay_reported" in rec["canonical_fields"]["action_signals"]


# --------------------------------------------------------------------------- #
# delays / accident / safety_violation — safety routed
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "fn,endpoint,raw,signal",
    [
        (
            dll.normalize_daily_log_delay,
            "daily-log-delays-review-routed",
            {
                "id": 1,
                "delay_type": "weather",
                "duration": 5,
                "comments": _FREETEXT_STRINGS[0],
                "created_by": _PERSON,
                "location": _LOCATION,
                "attachments": _ATTACH,
            },
            "delay",
        ),
        (
            dll.normalize_daily_log_accident,
            "daily-log-accident-review-routed",
            {
                "id": 2,
                "comments": _FREETEXT_STRINGS[0],
                "involved_name": "Synthetic Involved Person",
                "involved_company": "Synthetic Industries",
                "created_by": _PERSON,
                "location": _LOCATION,
                "attachments": _ATTACH,
            },
            "safety",
        ),
        (
            dll.normalize_daily_log_safety_violation,
            "daily-log-safety-violation-review-routed",
            {
                "id": 3,
                "comments": _FREETEXT_STRINGS[0],
                "safety_notice": _FREETEXT_STRINGS[3],
                "compliance_due": "2016-06-20",
                "issued_to": "Synthetic Industries",
                "subject": "hard hats",
                "created_by": _PERSON,
                "location": _LOCATION,
                "attachments": _ATTACH,
            },
            "safety",
        ),
    ],
)
def test_safety_routed_sections(fn, endpoint, raw, signal):
    rec = _norm(fn, endpoint, raw)
    assert rec["review_required"] is True
    assert rec.get("safety_route") is True
    assert signal in rec["canonical_fields"]["action_signals"]
    _assert_no_pii_leak(rec)


# --------------------------------------------------------------------------- #
# inspections — safety detection from inspection_type, inspector_name hashed
# --------------------------------------------------------------------------- #


def test_inspection_safety_detection_and_inspector_hashed():
    raw = {
        "id": 333675,
        "area": "Level 5",
        "comments": _FREETEXT_STRINGS[0],
        "inspecting_entity": "Safety",
        "inspection_type": "Safety",
        "inspector_name": "Synthetic Inspector",
        "created_by": _PERSON,
        "location": _LOCATION,
        "vendor": _VENDOR,
        "attachments": _ATTACH,
    }
    rec = _norm(dll.normalize_daily_log_inspection, "daily-log-inspections", raw)
    assert rec.get("safety_route") is True and rec["review_required"] is True
    assert "safety" in rec["canonical_fields"]["action_signals"]
    roles = {p["role"] for p in rec["canonical_fields"]["entities"]["people"]}
    assert "inspector" in roles
    _assert_no_pii_leak(rec)


def test_inspection_non_safety_is_medium():
    raw = {
        "id": 1,
        "inspection_type": "General",
        "inspecting_entity": "QA",
        "inspector_name": "Synthetic Inspector",
        "created_by": _PERSON,
    }
    rec = _norm(dll.normalize_daily_log_inspection, "daily-log-inspections", raw)
    assert rec.get("safety_route") is None and rec["review_required"] is False


# --------------------------------------------------------------------------- #
# visitor — subject (visitor name) is PII -> hashed; review required
# --------------------------------------------------------------------------- #


def test_visitor_subject_pii_hashed():
    raw = {
        "id": 333675,
        "begin_hour": 12,
        "end_hour": 14,
        "status": "pending",
        "details": _FREETEXT_STRINGS[2],
        "subject": "Synthetic Visitor (Glass Co.)",
        "created_by": _PERSON,
        "vendor": _VENDOR,
        "location": _LOCATION,
        "custom_fields": _CUSTOM_FIELDS,
        "permissions": {"can_update": True, "can_delete": False},
    }
    rec = _norm(dll.normalize_daily_log_visitor, "daily-log-visitor", raw)
    cf = rec["canonical_fields"]
    assert rec["review_required"] is True
    assert "subject_summary" in cf and "subject" not in cf
    assert "details_summary" in cf
    _assert_no_pii_leak(rec)


# --------------------------------------------------------------------------- #
# dumpster + dcr — structured, low/medium, edges present
# --------------------------------------------------------------------------- #


def test_dumpster_structured_and_edges():
    raw = {
        "id": 333675,
        "quantity_delivered": 5,
        "quantity_removed": 2,
        "comments": _FREETEXT_STRINGS[0],
        "created_by": _PERSON,
        "vendor": _VENDOR,
        "location": _LOCATION,
        "daily_log_segment": _SEGMENT,
        "attachments": _ATTACH,
    }
    rec = _norm(dll.normalize_daily_log_dumpster, "daily-log-dumpster", raw)
    cf = rec["canonical_fields"]
    assert rec["review_required"] is False
    assert cf["quantity_delivered"] == 5
    rels = {e["rel"] for e in cf["edges"]}
    assert {"created_by", "vendor", "at_location", "in_segment"} <= rels
    _assert_no_pii_leak(rec)


def test_dcr_preserves_hour_fields_and_hashes_notes():
    raw = {
        "id": 333675,
        "status": "pending",
        "apprentice_hours": "5.0",
        "foreman_hours": "5.0",
        "number_of_apprentice_workers": 4,
        "notes": _FREETEXT_STRINGS[1],
        "created_by": _PERSON,
        "vendor": _VENDOR,
        "trade": {"id": 999, "name": "09 - acoustical panels"},
        "location": _LOCATION,
        "custom_fields": _CUSTOM_FIELDS,
        "permissions": {"can_update": True, "can_delete": False},
    }
    rec = _norm(dll.normalize_daily_log_dcr, "daily-log-dcrs", raw)
    cf = rec["canonical_fields"]
    assert cf["apprentice_hours"] == "5.0" and cf["number_of_apprentice_workers"] == 4
    assert "notes_summary" in cf and "notes" not in cf
    _assert_no_pii_leak(rec)


# --------------------------------------------------------------------------- #
# contract guards
# --------------------------------------------------------------------------- #


def test_missing_id_raises():
    with pytest.raises(ValueError):
        _norm(dll.normalize_daily_log_weather, "daily-log-weather", {"date": "2016-05-19"})


def test_registry_covers_all_eleven_sections():
    assert len(dll.NORMALIZER_BY_ENDPOINT) == 11
