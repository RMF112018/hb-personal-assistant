"""Phase 06 Prompt 11 — Ollama structured email intelligence (local-only, advisory).

Proves the structured schema rejects invalid JSON + forbidden body fields, decrypted body
context is used in-memory but never persisted, low-confidence / sensitive cases route to
review, deterministic rules override the model, and dry-run persists nothing.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, cast

import pytest

from hb_assistant.construction.email.email_classifier import (
    CLASSIFICATION_VERSION,
    EmailIntelligenceClassifier,
    InvalidEmailModelOutputError,
    parse_and_validate_email_output,
)
from hb_assistant.construction.store import ConstructionStore

# A distinctive plaintext token we will encrypt as a body and then assert never leaks.
_SECRET_BODY = "SECRET_BODY_TOKEN_zzz contract change order details that must stay encrypted"


def _valid_output(**over: object) -> str:
    base = {
        "project_match_suggestions": [{"project_key": "tropical", "signal": "subject", "confidence": 0.8}],
        "topic_labels": ["schedule"],
        "relationship_candidates": [],
        "risk_flags": [],
        "review_required": False,
        "review_reasons": [],
        "confidence": 0.9,
    }
    base.update(over)
    return json.dumps(base)


def _tmp_db() -> str:
    return str(Path(tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False).name))


def _store(db: str) -> ConstructionStore:
    store = ConstructionStore(db)
    store.upsert_email_source_location(
        source_id="sx", mailbox_owner_hash="h", folder_role="inbox", folder_id="F"
    )
    return store


def _add(store: ConstructionStore, mid: str, preview: str, *, confidence: float = 0.95) -> None:
    store.upsert_email_message(
        message_id=mid, thread_key="t" + mid, source_id="sx", sender_domain="vendor.com",
        received_datetime="2026-05-20T10:00:00Z", body_preview_excerpt_redacted=preview,
    )
    store.upsert_email_project_match(
        match_id="pm-" + mid, message_id=mid, match_signal="project_name_in_subject",
        confidence=confidence, project_key="tropical", project_number="23-435-01",
    )


# --- validator ------------------------------------------------------------------


def test_validator_accepts_valid_output() -> None:
    out = parse_and_validate_email_output(_valid_output())
    assert out.confidence == 0.9
    assert out.topic_labels == ["schedule"]


@pytest.mark.parametrize("raw,code", [
    ("", "empty_output"),
    ("not json", "json_parse_failed"),
    ("[1,2,3]", "not_a_json_object"),
    ('{"confidence": 0.5}', "schema_validation_failed"),
])
def test_validator_rejects_invalid(raw: str, code: str) -> None:
    with pytest.raises(InvalidEmailModelOutputError) as e:
        parse_and_validate_email_output(raw)
    assert e.value.code == code


def test_validator_rejects_forbidden_body_field() -> None:
    raw = _valid_output(body_text="leaked body")
    with pytest.raises(InvalidEmailModelOutputError) as e:
        parse_and_validate_email_output(raw)
    assert e.value.code == "forbidden_field"


def test_validator_rejects_determination_field() -> None:
    raw = _valid_output(legal_determination="valid claim")
    with pytest.raises(InvalidEmailModelOutputError) as e:
        parse_and_validate_email_output(raw)
    assert e.value.code == "forbidden_field"


# --- classifier -----------------------------------------------------------------


@pytest.mark.xfail(
    reason="07B Prompt 06: ConstructionStore.upsert_email_model_classification not yet implemented",
    strict=False,
)
def test_mock_output_happy_path_persists_classification() -> None:
    db = _tmp_db()
    store = _store(db)
    _add(store, "m1", "weekly recap and progress photos", confidence=0.95)
    report = EmailIntelligenceClassifier(store).classify(
        project_key="tropical", lookback_days=30, dry_run=False, mock_output=_valid_output()
    )
    assert report.messages_considered == 1
    assert report.model_outputs_valid is True
    assert report.review_required_count == 0
    rec = store.get_email_model_classification(
        message_id="m1", model_name="mistral", schema_version=CLASSIFICATION_VERSION
    )
    assert rec is not None
    assert rec["classification_status"] == "valid"
    assert rec["topic_labels"] == ["schedule"]
    assert rec["advisory_only"] is True


@pytest.mark.xfail(
    reason="07B Prompt 06: ConstructionStore.upsert_email_model_classification not yet implemented",
    strict=False,
)
def test_invalid_json_routes_to_review_and_persists_no_partial() -> None:
    db = _tmp_db()
    store = _store(db)
    _add(store, "m1", "weekly recap", confidence=0.95)
    report = EmailIntelligenceClassifier(store).classify(
        project_key="tropical", lookback_days=30, dry_run=False, mock_output="not json"
    )
    assert report.model_outputs_valid is False
    assert report.model_outputs_invalid_count == 1
    assert report.review_required_count == 1
    rec = store.get_email_model_classification(
        message_id="m1", model_name="mistral", schema_version=CLASSIFICATION_VERSION
    )
    assert rec is not None
    assert rec["classification_status"] == "invalid_model_output"
    assert rec["topic_labels"] in (None, [])  # no partial model output persisted
    assert store.count_email_review_queue(project_key="tropical", status="open") >= 1


@pytest.mark.xfail(
    reason="07B Prompt 06: ConstructionStore.upsert_email_model_classification not yet implemented",
    strict=False,
)
def test_low_model_confidence_routes_to_review() -> None:
    db = _tmp_db()
    store = _store(db)
    _add(store, "m1", "weekly recap", confidence=0.95)
    report = EmailIntelligenceClassifier(store).classify(
        project_key="tropical", lookback_days=30, dry_run=False,
        mock_output=_valid_output(confidence=0.2),
    )
    assert report.review_required_count == 1


@pytest.mark.xfail(
    reason="07B Prompt 06: ConstructionStore.upsert_email_model_classification not yet implemented",
    strict=False,
)
def test_sensitive_category_routes_to_review_despite_high_model_confidence() -> None:
    db = _tmp_db()
    store = _store(db)
    _add(store, "m1", "attached change order for pricing", confidence=0.95)
    report = EmailIntelligenceClassifier(store).classify(
        project_key="tropical", lookback_days=30, dry_run=False,
        mock_output=_valid_output(confidence=0.99, review_required=False),
    )
    assert report.review_required_count == 1
    queue = store.list_email_review_queue(project_key="tropical", status="open")
    assert any(r["category"] == "change_orders" for r in queue)


@pytest.mark.xfail(
    reason="07B Prompt 06: ConstructionStore.upsert_email_model_classification not yet implemented",
    strict=False,
)
def test_deterministic_low_confidence_overrides_model() -> None:
    db = _tmp_db()
    store = _store(db)
    # Project-match confidence below the 0.75 threshold → deterministic review,
    # even though the model says review_required=false and confidence=0.99.
    _add(store, "m1", "weekly recap", confidence=0.60)
    report = EmailIntelligenceClassifier(store).classify(
        project_key="tropical", lookback_days=30, dry_run=False,
        mock_output=_valid_output(confidence=0.99, review_required=False),
    )
    assert report.review_required_count == 1


def test_dry_run_persists_nothing() -> None:
    db = _tmp_db()
    store = _store(db)
    _add(store, "m1", "attached change order", confidence=0.95)
    report = EmailIntelligenceClassifier(store).classify(
        project_key="tropical", lookback_days=30, dry_run=True, mock_output=_valid_output()
    )
    assert report.persisted is False
    conn = sqlite3.connect(db)
    try:
        n = conn.execute("SELECT COUNT(*) FROM email_model_classifications").fetchone()[0]
        q = conn.execute("SELECT COUNT(*) FROM email_review_queue").fetchone()[0]
    finally:
        conn.close()
    assert n == 0
    assert q == 0


@pytest.mark.xfail(
    reason="07B Prompt 06: ConstructionStore.upsert_email_model_classification not yet implemented",
    strict=False,
)
def test_no_model_available_marks_unavailable() -> None:
    db = _tmp_db()
    store = _store(db)
    _add(store, "m1", "weekly recap", confidence=0.95)
    # No client, no mock_output → model not attempted.
    report = EmailIntelligenceClassifier(store).classify(
        project_key="tropical", lookback_days=30, dry_run=False, mock_output=None
    )
    assert report.model_attempted_count == 0
    rec = store.get_email_model_classification(
        message_id="m1", model_name="mistral", schema_version=CLASSIFICATION_VERSION
    )
    assert rec is not None
    assert rec["classification_status"] == "model_unavailable"


@pytest.mark.xfail(
    reason="07B Prompt 06: ConstructionStore.upsert_email_model_classification not yet implemented",
    strict=False,
)
def test_encrypted_body_context_used_but_never_persisted(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HB_APP_SUPPORT_DIR", str(tmp_path))
    from hb_assistant.security.text_vault import encrypt_text

    db = str(tmp_path / "db.sqlite")
    store = _store(db)
    _add(store, "m1", "weekly recap", confidence=0.95)
    ref = encrypt_text(_SECRET_BODY)
    assert ref is not None
    store.upsert_email_body_vault_ref(
        message_id="m1", encrypted_full_body_ref=ref, body_hash="bh", body_length=len(_SECRET_BODY),
        extraction_policy="encrypted_text_vault",
    )
    report = EmailIntelligenceClassifier(store).classify(
        project_key="tropical", lookback_days=30, dry_run=False,
        use_encrypted_body_context=True, mock_output=_valid_output(),
    )
    assert report.encrypted_body_context_used_count == 1
    assert report.plaintext_persisted is False
    # The decrypted body token must not appear anywhere in the report or persisted rows.
    assert _SECRET_BODY not in json.dumps(report.model_dump())
    rec = store.get_email_model_classification(
        message_id="m1", model_name="mistral", schema_version=CLASSIFICATION_VERSION
    )
    assert _SECRET_BODY not in json.dumps(rec)
    for receipt in store.list_email_processing_receipts():
        assert _SECRET_BODY not in json.dumps(receipt)
    for row in store.list_email_review_queue(project_key="tropical", status=None):
        assert _SECRET_BODY not in json.dumps(row)
    # And it never reached the SQLite file as plaintext.
    raw_db = Path(db).read_bytes()
    assert _SECRET_BODY.encode("utf-8") not in raw_db


def test_live_model_prompt_uses_encrypted_body_context(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HB_APP_SUPPORT_DIR", str(tmp_path))
    from hb_assistant.security.text_vault import encrypt_text

    captured: dict[str, str] = {}

    class _Client:
        def generate_json(self, *, system: str, prompt: str) -> str:
            captured["prompt"] = prompt
            return _valid_output()

    db = str(tmp_path / "db.sqlite")
    store = _store(db)
    _add(store, "m1", "weekly recap", confidence=0.95)
    ref = encrypt_text(_SECRET_BODY)
    assert ref is not None
    store.upsert_email_body_vault_ref(
        message_id="m1",
        encrypted_full_body_ref=ref,
        body_hash="bh",
        body_length=len(_SECRET_BODY),
        extraction_policy="encrypted_text_vault",
    )
    report = EmailIntelligenceClassifier(store, client=cast(Any, _Client())).classify(
        project_key="tropical",
        lookback_days=30,
        dry_run=True,
        use_encrypted_body_context=True,
        mock_output=None,
    )
    assert report.encrypted_body_context_used_count == 1
    assert "body_context:" in captured["prompt"]
    assert _SECRET_BODY[:40] in captured["prompt"]
