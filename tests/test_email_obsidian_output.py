"""Prompt 12 email Obsidian output tests (safe grouped projections)."""

from __future__ import annotations

import json
from pathlib import Path

from hb_assistant.construction.email.obsidian_projection import EmailObsidianProjector
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.security.text_vault import encrypt_text


def _seed_store(db: str, tmp_path: Path) -> ConstructionStore:
    store = ConstructionStore(db)
    store.upsert_email_source_location(
        source_id="sx",
        mailbox_owner_hash="owner",
        folder_role="inbox",
        folder_id="folder-1",
    )
    store.upsert_email_message(
        message_id="m1",
        thread_key="t1",
        source_id="sx",
        sender_domain="vendor.com",
        subject_redacted="Project tropical weekly schedule",
        received_datetime="2026-05-20T10:00:00Z",
        web_link="https://outlook.example/messages/m1",
        body_preview_excerpt_redacted="change order and schedule update",
    )
    store.upsert_email_project_match(
        match_id="pm1",
        message_id="m1",
        match_signal="project_name_in_subject",
        confidence=0.92,
        project_key="tropical",
        project_number="23-435-01",
    )
    store.upsert_email_relationship_candidate(
        candidate_id="rc1",
        message_id="m1",
        candidate_type="change_order",
        match_signal="body_preview",
        confidence=0.78,
        project_key="tropical",
        review_required=True,
    )
    store.enqueue_email_review_item(
        review_id="rv1",
        message_id="m1",
        category="change_orders",
        sensitivity="high",
        reason="sensitive category",
        suggested_action="manual_review",
        confidence=0.92,
        project_key="tropical",
    )
    store.insert_email_processing_receipt(
        receipt_id="r1",
        operation="index",
        status="ok",
        run_id="run-1",
        project_key="tropical",
        detail={"messages_discovered": 1, "messages_indexed": 1, "folders_scanned": 1},
    )
    ref = encrypt_text("SECRET_SENTINEL_FULL_BODY_DO_NOT_LEAK")
    assert ref is not None
    store.upsert_email_body_vault_ref(
        message_id="m1",
        encrypted_full_body_ref=ref,
        body_hash="h1",
        body_length=37,
        extraction_policy="encrypted_text_vault",
    )
    return store


def test_projector_generates_grouped_safe_dry_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HB_APP_SUPPORT_DIR", str(tmp_path / "app-support"))
    monkeypatch.setenv("HB_CONSTRUCTION_VAULT_ROOT", str(tmp_path / "vault"))
    db = str(tmp_path / "db.sqlite")
    store = _seed_store(db, tmp_path)

    report = EmailObsidianProjector(store).project(
        project_key="tropical",
        include_encrypted_body_status=True,
        dry_run=True,
    )
    assert report.notes_planned >= 3
    assert report.messages_referenced == 1
    assert report.plaintext_body_written is False
    assert report.encrypted_body_refs_referenced == 0
    # Grouped artifacts, not one note per email.
    assert report.notes_planned < 10
    assert any("Correspondence Intelligence.md" in p for p in report.paths)


def test_projector_apply_writes_marker_bounded_without_plaintext(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("HB_APP_SUPPORT_DIR", str(tmp_path / "app-support"))
    vault = tmp_path / "vault"
    monkeypatch.setenv("HB_CONSTRUCTION_VAULT_ROOT", str(vault))
    db = str(tmp_path / "db.sqlite")
    store = _seed_store(db, tmp_path)

    report = EmailObsidianProjector(store).project(
        project_key="tropical",
        include_encrypted_body_status=True,
        dry_run=False,
    )
    assert report.notes_written == report.notes_planned
    for p in report.paths:
        text = Path(p).read_text(encoding="utf-8").lower()
        assert "secret_sentinel_full_body_do_not_leak" not in text
        assert "encrypted_full_body_ref" not in text
        assert "raw email body" not in text
        assert "full_body_plaintext" not in text


def test_projector_json_report_serializable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HB_APP_SUPPORT_DIR", str(tmp_path / "app-support"))
    monkeypatch.setenv("HB_CONSTRUCTION_VAULT_ROOT", str(tmp_path / "vault"))
    db = str(tmp_path / "db.sqlite")
    store = _seed_store(db, tmp_path)
    report = EmailObsidianProjector(store).project(project_key="tropical", dry_run=True)
    payload = json.loads(report.model_dump_json())
    assert payload["plaintext_body_written"] is False
    assert payload["encrypted_body_status_included"] is True
