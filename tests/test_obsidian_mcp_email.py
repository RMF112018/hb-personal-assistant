"""Email/.eml tools for the UI-managed Obsidian MCP server."""

# ruff: noqa: I001,E402

from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.config import load_config
from hb_assistant.obsidian_mcp.eml import email_inventory, parse_email, read_eml
from hb_assistant.obsidian_mcp.mutations import recent_read_receipts
from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError


def _make_eml(path: Path, *, html: bool = False, attachment: bool = False) -> None:
    msg = EmailMessage()
    msg["Subject"] = "RFI 142 — canopy detail and schedule impact"
    msg["From"] = "Jane Engineer <jane@example.com>"
    msg["To"] = "Bobby Fetting <bobby@example.com>"
    msg["Cc"] = "PM <pm@example.com>"
    msg["Date"] = "Mon, 15 Jun 2026 09:00:00 -0400"
    text = (
        "Please confirm the crane delivery by Friday. Call me at 561-555-1234.\n"
        "We decided to resequence the slab pours. The owner approved a change order.\n"
        "Submittal 07 is pending and there is a $25,000 cost exposure on switchgear.\n"
    )
    if html:
        msg.set_content(f"<html><body><p>{text}</p><script>x()</script></body></html>", subtype="html")
    else:
        msg.set_content(text)
    if attachment:
        msg.add_attachment(b"PDFDATA", maintype="application", subtype="pdf", filename="detail.pdf")
    path.write_bytes(bytes(msg))


def _write_config(tmp_path: Path, vault: Path) -> Path:
    app_support = tmp_path / "app-support"
    cfg = tmp_path / "config.yml"
    cfg.write_text(
        "\n".join(
            [
                "paths:",
                f"  application_support_root: {app_support.as_posix()!r}",
                f"  obsidian_vault: {vault.as_posix()!r}",
            ]
        ),
        encoding="utf-8",
    )
    return cfg


def _setup(tmp_path, monkeypatch, *, html=False, attachment=False, count=1):
    vault = tmp_path / "vault"
    inbox = vault / "Work" / "Email" / "inbox"
    inbox.mkdir(parents=True)
    for i in range(count):
        _make_eml(inbox / f"msg{i}.eml", html=html, attachment=attachment)
    (vault / ".obsidian").mkdir()
    (vault / ".obsidian" / "secret.eml").write_bytes(b"From: x\n\nhidden")
    cfg = _write_config(tmp_path, vault)
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    return load_config(), vault, inbox


# ---------------------------------------------------------------------------
# read_eml
# ---------------------------------------------------------------------------
def test_read_eml_plain(tmp_path, monkeypatch):
    config, _vault, _inbox = _setup(tmp_path, monkeypatch)
    result = read_eml(config, path="Work/Email/inbox/msg0.eml")
    assert result["subject"].startswith("RFI 142")
    assert result["from"] == "Jane Engineer <jane@example.com>"
    assert "crane" in result["body_preview"].lower()
    assert any("crane" in a.lower() or "confirm" in a.lower() for a in result["detected_action_items"])
    assert result["attachments"] == []  # metadata-only and not requested


def test_read_eml_html_converted(tmp_path, monkeypatch):
    config, _vault, _inbox = _setup(tmp_path, monkeypatch, html=True)
    result = read_eml(config, path="Work/Email/inbox/msg0.eml")
    assert "crane" in result["body_preview"].lower()
    assert "<p>" not in result["body_preview"]
    assert "x()" not in result["body_preview"]  # script content stripped
    assert "html_converted" in result["warnings"]


def test_read_eml_attachments_metadata_only(tmp_path, monkeypatch):
    config, _vault, _inbox = _setup(tmp_path, monkeypatch, attachment=True)
    result = read_eml(config, path="Work/Email/inbox/msg0.eml", include_attachments=True)
    assert result["attachments"][0]["filename"] == "detail.pdf"
    assert result["attachments"][0]["content_type"] == "application/pdf"
    assert "PDFDATA" not in str(result)  # content never returned


def test_read_eml_redaction_optional(tmp_path, monkeypatch):
    config, _vault, _inbox = _setup(tmp_path, monkeypatch)
    raw = read_eml(config, path="Work/Email/inbox/msg0.eml")
    assert "561-555-1234" in raw["body_preview"]  # default: no redaction
    red = read_eml(
        config,
        path="Work/Email/inbox/msg0.eml",
        redact_email_addresses=True,
        redact_phone_numbers=True,
    )
    assert "561-555-1234" not in red["body_preview"]
    assert "[redacted-phone]" in red["body_preview"]


def test_read_eml_max_body_chars(tmp_path, monkeypatch):
    config, _vault, _inbox = _setup(tmp_path, monkeypatch)
    result = read_eml(config, path="Work/Email/inbox/msg0.eml", max_body_chars=20)
    assert len(result["body_preview"]) <= 20
    assert "body_truncated" in result["warnings"]


def test_read_eml_rejects_non_eml_and_protected(tmp_path, monkeypatch):
    config, vault, _inbox = _setup(tmp_path, monkeypatch)
    (vault / "Work" / "note.md").write_text("# note\n", encoding="utf-8")
    with pytest.raises(ObsidianMcpToolError) as exc:
        read_eml(config, path="Work/note.md")
    assert exc.value.code == "not_an_eml_file"
    with pytest.raises(ObsidianMcpToolError) as exc2:
        read_eml(config, path=".obsidian/secret.eml", operator_mode=False)
    assert exc2.value.code == "protected_path_blocked"


# ---------------------------------------------------------------------------
# email_inventory
# ---------------------------------------------------------------------------
def test_email_inventory_metadata_only_and_caps(tmp_path, monkeypatch):
    config, _vault, _inbox = _setup(tmp_path, monkeypatch, count=3)
    result = email_inventory(config, root_path="Work/Email/inbox", max_files=2, principal_kind="oauth")
    assert result["count"] == 2
    assert result["truncated"] is True
    first = result["emails"][0]
    assert "subject" in first and "body_preview" not in first  # no bodies by default
    receipts = recent_read_receipts(5)
    assert receipts[-1]["tool_name"] == "vault_email_inventory"
    assert receipts[-1]["principal_kind"] == "oauth"


def test_email_inventory_excludes_protected(tmp_path, monkeypatch):
    config, _vault, _inbox = _setup(tmp_path, monkeypatch)
    result = email_inventory(config, root_path="", max_depth=10)
    paths = {e["path"] for e in result["emails"]}
    assert "Work/Email/inbox/msg0.eml" in paths
    assert not any(p.startswith(".obsidian") for p in paths)


# ---------------------------------------------------------------------------
# parse_email
# ---------------------------------------------------------------------------
def test_parse_email_extraction_categories(tmp_path, monkeypatch):
    config, _vault, _inbox = _setup(tmp_path, monkeypatch)
    result = parse_email(config, path="Work/Email/inbox/msg0.eml")
    assert result["subject"].startswith("RFI 142")
    assert result["action_items"]
    assert any("approved" in d.lower() or "decided" in d.lower() for d in result["decisions"])
    assert result["rfis"]  # "RFI 142" matched
    assert result["submittals"]  # "Submittal 07"
    assert result["cost_exposure"]  # "$25,000"
    assert "bobby@example.com" in str(result["people"]) or "Bobby Fetting" in str(result["people"])


def test_parse_email_respects_extract_subset(tmp_path, monkeypatch):
    config, _vault, _inbox = _setup(tmp_path, monkeypatch)
    result = parse_email(config, path="Work/Email/inbox/msg0.eml", extract=["summary"])
    assert "summary" in result
    assert "rfis" not in result
    assert "action_items" not in result
