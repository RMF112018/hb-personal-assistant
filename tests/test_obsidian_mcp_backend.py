"""UI-managed Obsidian MCP backend tests."""

# ruff: noqa: I001,E402

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.obsidian_mcp.config import load_config
from hb_assistant.obsidian_mcp.mutations import create_note, patch_note, recent_mutations, sha256_file
from hb_assistant.obsidian_mcp.tools import read_file, search_vault
from hb_assistant.store.migrator import SQLiteMigrator



def _mcp_json_payload(response):
    """Parse MCP responses from either SSE-style or json_response=True mode."""
    text = response.text.strip()
    if "data: " in text:
        data = text.split("data: ", 1)[1].strip()
        return json.loads(data)
    return response.json()


FORBIDDEN = ("secret-token", "access_token", "refresh_token", "client_secret")


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


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Path]:
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    (vault / "Projects").mkdir()
    (vault / "Projects" / "Scope.md").write_text(
        "# Scope\n\nUnderground conduit belongs to electrical.\n\n## Notes\n\nProcurement lead time.",
        encoding="utf-8",
    )
    (vault / "Projects" / "notes.txt").write_text("procurement conduit status", encoding="utf-8")
    cfg = _write_config(tmp_path, vault)
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    db = str(tmp_path / "api.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return TestClient(create_app(db_path=db)), vault


def _assert_safe(payload: Any) -> None:
    serialized = json.dumps(payload, default=str)
    for marker in FORBIDDEN:
        assert marker not in serialized


def test_config_update_redacts_token_and_persists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, vault = _client(tmp_path, monkeypatch)
    patch = {
        "enabled": True,
        "vault_root": str(vault),
        "bearer_token": "secret-token",
        "max_file_mb": 5,
        "max_result_chars": 500,
    }
    res = client.patch(
        "/api/settings/obsidian-mcp/config",
        json=patch,
        headers={"X-HB-UI-Role": "operator"},
    )
    assert res.status_code == 200
    body = res.json()
    _assert_safe(body)
    assert body["config"]["token_configured"] is True
    assert "bearer_token" not in body["config"]
    assert load_config().bearer_token == "secret-token"

    reread = client.get("/api/settings/obsidian-mcp/config").json()
    _assert_safe(reread)
    assert reread["config"]["token_configured"] is True


def test_status_health_tools_and_grok_config_are_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, vault = _client(tmp_path, monkeypatch)
    client.patch(
        "/api/settings/obsidian-mcp/config",
        json={"enabled": True, "vault_root": str(vault), "bearer_token": "secret-token"},
        headers={"X-HB-UI-Role": "operator"},
    )
    for path in (
        "/api/settings/obsidian-mcp/status",
        "/api/settings/obsidian-mcp/tools",
        "/api/settings/obsidian-mcp/grok-config",
        "/api/settings/obsidian-mcp/read-receipts",
    ):
        res = client.get(path)
        assert res.status_code == 200
        _assert_safe(res.json())
    tools_payload = client.get("/api/settings/obsidian-mcp/tools").json()
    assert all("category" in tool for tool in tools_payload["tools"])
    assert client.get("/api/settings/obsidian-mcp/read-receipts").json()["surface"] == "settings.obsidian_mcp.read_receipts"

    health = client.post("/api/settings/obsidian-mcp/health-check").json()
    _assert_safe(health)
    assert "checks" in health
    assert any(check["name"] == "tool_registry" for check in health["checks"])
    grok = client.get("/api/settings/obsidian-mcp/grok-config").json()
    assert grok["token_value_returned"] is False
    assert grok["mcp_config"]["mcpServers"]["hb-obsidian-hybrid"]["headers"]["Authorization"] == "Bearer <configured-token>"


def test_streamable_http_mount_lists_phase1_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("mcp")
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    cfg = _write_config(tmp_path, vault)
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg))
    db = str(tmp_path / "api.sqlite")
    SQLiteMigrator(db_path=db).apply()

    headers = {"Accept": "application/json, text/event-stream", "Host": "127.0.0.1:3010"}
    with TestClient(create_app(db_path=db), base_url="http://127.0.0.1:3010") as client:
        client.patch(
            "/api/settings/obsidian-mcp/config",
            json={
                "enabled": True,
                "vault_root": str(vault),
                "writes_enabled": True,
                "vault_markdown_write_enabled": True,
            },
            headers={"X-HB-UI-Role": "operator"},
        )
        initialized = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "hb-test", "version": "1.0"},
                },
            },
            headers=headers,
        )
        assert initialized.status_code == 200
        session_id = initialized.headers.get("mcp-session-id")

        session_headers = dict(headers)
        if session_id:
            session_headers["mcp-session-id"] = session_id

        initialized_notification = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=session_headers,
        )
        assert initialized_notification.status_code in {200, 202}
        assert initialized_notification.status_code != 421

        tools = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            headers=session_headers,
        )
        assert tools.status_code == 200
        assert tools.status_code != 421
        payload = _mcp_json_payload(tools)
        assert [tool["name"] for tool in payload["result"]["tools"]] == [
            "list_directory",
            "search_vault",
            "read_file",
            "create_note",
            "patch_note",
            "vault_map",
            "vault_summarize_note",
            "vault_summarize_folder",
            "vault_read_eml",
            "vault_email_inventory",
            "vault_parse_email",
            "vault_read_frontmatter",
            "vault_update_frontmatter",
            "vault_search_by_properties",
            "vault_dataview_query",
            "vault_get_backlinks",
            "vault_get_unlinked_mentions",
            "vault_get_note_graph",
            "vault_create_note_from_template",
            "vault_append_to_daily_note",
            "vault_semantic_search",
            "vault_move_note_plan",
            "vault_move_note_apply",
            "vault_rename_note_plan",
            "vault_rename_note_apply",
            "vault_archive_note_plan",
            "vault_archive_note_apply",
            "vault_delete_note_plan",
            "vault_extract_action_items",
            "vault_project_status_summary",
            "vault_extract_project_mentions",
            "vault_curation_plan",
            "vault_curation_apply",
            "vault_create_moc_plan",
            "vault_auto_link_plan",
            "vault_bulk_tagging_plan",
            "vault_email_to_note_plan",
            "vault_email_to_note_apply",
            "search_sources",
            "search_knowledge",
            "source_index_status",
            "rebuild_source_index",
        ]

        create = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "create_note",
                    "arguments": {"path": "Managed/Protocol.md", "content": "# Protocol\n\ncreated"},
                },
            },
            headers=session_headers,
        )
        assert create.status_code == 200
        assert (vault / "Managed" / "Protocol.md").exists()
        assert "# Protocol" not in create.text
        current_sha = sha256_file(vault / "Managed" / "Protocol.md")

        patch = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "patch_note",
                    "arguments": {
                        "path": "Managed/Protocol.md",
                        "content": "# Protocol\n\nreplaced",
                        "expected_sha256": current_sha,
                    },
                },
            },
            headers=session_headers,
        )
        assert patch.status_code == 200
        assert "replaced" not in patch.text
        assert "replaced" in (vault / "Managed" / "Protocol.md").read_text(encoding="utf-8")

        client.patch(
            "/api/settings/obsidian-mcp/config",
            json={"writes_enabled": False},
            headers={"X-HB-UI-Role": "operator"},
        )
        blocked = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "create_note",
                    "arguments": {"path": "Managed/Blocked.md", "content": "# Blocked"},
                },
            },
            headers=session_headers,
        )
        assert blocked.status_code == 200
        assert "writes_disabled" in blocked.text
        assert "# Blocked" not in blocked.text


def test_lifecycle_and_test_actions_work_from_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, vault = _client(tmp_path, monkeypatch)
    client.patch(
        "/api/settings/obsidian-mcp/config",
        json={"vault_root": str(vault), "max_result_chars": 2000},
        headers={"X-HB-UI-Role": "operator"},
    )
    assert client.post("/api/settings/obsidian-mcp/enable", headers={"X-HB-UI-Role": "operator"}).status_code == 200

    listed = client.post(
        "/api/settings/obsidian-mcp/test/list-directory",
        json={"path": "Projects", "recursive": True, "extensions": ["md"]},
        headers={"X-HB-UI-Role": "operator"},
    )
    assert listed.status_code == 200
    assert listed.json()["result"]["files"][0]["path"] == "Projects/Scope.md"

    searched = client.post(
        "/api/settings/obsidian-mcp/test/search",
        json={"query": "conduit", "path_scope": "Projects"},
        headers={"X-HB-UI-Role": "operator"},
    ).json()
    assert searched["ok"] is True
    assert searched["result"]["results"][0]["path"] == "Projects/Scope.md"

    read = client.post(
        "/api/settings/obsidian-mcp/test/read-file",
        json={"path": "Projects/Scope.md", "section": "Notes", "max_chars": 50},
        headers={"X-HB-UI-Role": "operator"},
    ).json()
    assert read["ok"] is True
    assert "Procurement" in read["result"]["content"]


def test_autonomous_markdown_writes_are_policy_gated_and_audited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, vault = _client(tmp_path, monkeypatch)
    client.patch(
        "/api/settings/obsidian-mcp/config",
        json={"vault_root": str(vault), "writes_enabled": False, "vault_markdown_write_enabled": False},
        headers={"X-HB-UI-Role": "operator"},
    )
    disabled = client.post("/api/settings/obsidian-mcp/test/write-smoke", headers={"X-HB-UI-Role": "operator"}).json()
    assert disabled["ok"] is False
    assert disabled["error_code"] == "writes_disabled"

    client.patch(
        "/api/settings/obsidian-mcp/config",
        json={
            "writes_enabled": True,
            "vault_markdown_write_enabled": True,
            "max_write_chars": 1000,
            "backup_before_replace": True,
        },
        headers={"X-HB-UI-Role": "operator"},
    )
    readiness = client.post("/api/settings/obsidian-mcp/write-readiness").json()
    assert readiness["ok"] is True
    smoke = client.post("/api/settings/obsidian-mcp/test/write-smoke", headers={"X-HB-UI-Role": "operator"}).json()
    assert smoke["ok"] is True
    assert (vault / "MCP Write Smoke" / "hb-mcp-write-smoke.md").exists()
    serialized = json.dumps(client.get("/api/settings/obsidian-mcp/mutations").json(), default=str)
    assert "managed note proves" not in serialized
    assert "secret-token" not in serialized


def test_create_and_patch_note_enforce_sha_backups_and_markdown_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _client_obj, vault = _client(tmp_path, monkeypatch)
    cfg = load_config().model_copy(
        update={
            "writes_enabled": True,
            "vault_markdown_write_enabled": True,
            "max_write_chars": 1000,
            "backup_before_replace": True,
        }
    )
    created = create_note(cfg, path="Anywhere/New Note.md", content="# New\n\nsafe body", caller_surface="ui_test")
    assert created["path"] == "Anywhere/New Note.md"
    note = vault / "Anywhere" / "New Note.md"
    assert note.exists()
    old_sha = sha256_file(note)

    try:
        create_note(cfg, path="Anywhere/New Note.md", content="# New", overwrite=True, caller_surface="ui_test")
    except Exception as exc:
        assert getattr(exc, "code", None) == "expected_sha256_required"
    else:
        raise AssertionError("overwrite without expected_sha256 should fail")

    try:
        patch_note(cfg, path="Anywhere/New Note.md", content="# Changed", expected_sha256="bad", caller_surface="ui_test")
    except Exception as exc:
        assert getattr(exc, "code", None) == "sha256_mismatch"
    else:
        raise AssertionError("SHA mismatch should fail")
    assert sha256_file(note) == old_sha

    patched = patch_note(
        cfg,
        path="Anywhere/New Note.md",
        content="# Changed\n\nreplacement",
        expected_sha256=old_sha,
        caller_surface="ui_test",
    )
    assert patched["old_sha256"] == old_sha
    assert patched["backup_path"]
    assert Path(str(patched["backup_path"])).exists()
    assert not list(note.parent.glob(".*.hb-mcp-*.tmp"))

    try:
        create_note(cfg, path="Anywhere/raw.txt", content="no", caller_surface="ui_test")
    except Exception as exc:
        assert getattr(exc, "code", None) == "markdown_writes_only"
    else:
        raise AssertionError("non-Markdown writes should fail")


def test_write_policy_blocks_protected_hidden_traversal_and_symlinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _client_obj, vault = _client(tmp_path, monkeypatch)
    outside = tmp_path / "outside"
    outside.mkdir()
    (vault / "linkdir").symlink_to(outside, target_is_directory=True)
    cfg = load_config().model_copy(
        update={"writes_enabled": True, "vault_markdown_write_enabled": True, "max_write_chars": 1000}
    )
    cases = {
        "/tmp/nope.md": "absolute_paths_not_allowed",
        "../nope.md": "path_traversal_not_allowed",
        ".obsidian/config.md": "protected_path_blocked",
        ".hidden/note.md": "hidden_path_blocked",
        "linkdir/note.md": "path_outside_vault_root",
    }
    for path, code in cases.items():
        try:
            create_note(cfg, path=path, content="# blocked", caller_surface="ui_test")
        except Exception as exc:
            assert getattr(exc, "code", None) == code
        else:
            raise AssertionError(f"{path} should fail")

    serialized = json.dumps(recent_mutations(20), default=str)
    assert "# blocked" not in serialized
    assert str(tmp_path) not in serialized


def test_path_traversal_and_symlink_escape_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, vault = _client(tmp_path, monkeypatch)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    (vault / "bad-link.txt").symlink_to(outside)
    client.patch(
        "/api/settings/obsidian-mcp/config",
        json={"vault_root": str(vault)},
        headers={"X-HB-UI-Role": "operator"},
    )
    traversal = client.post(
        "/api/settings/obsidian-mcp/test/read-file",
        json={"path": "../outside.txt"},
        headers={"X-HB-UI-Role": "operator"},
    ).json()
    assert traversal["ok"] is False
    assert traversal["error_code"] == "path_traversal_not_allowed"

    symlink = client.post(
        "/api/settings/obsidian-mcp/test/read-file",
        json={"path": "bad-link.txt"},
        headers={"X-HB-UI-Role": "operator"},
    ).json()
    assert symlink["ok"] is False
    assert symlink["error_code"] == "path_outside_vault_root"


def test_file_size_cap_blocks_large_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, vault = _client(tmp_path, monkeypatch)
    big = vault / "big.txt"
    big.write_text("x" * 2048, encoding="utf-8")
    client.patch(
        "/api/settings/obsidian-mcp/config",
        json={"vault_root": str(vault), "max_file_mb": 1, "max_result_chars": 100},
        headers={"X-HB-UI-Role": "operator"},
    )
    # Force a tiny cap after validation to exercise byte cap without huge fixture.
    cfg = load_config().model_copy(update={"max_file_mb": 0.000001})
    from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError

    with pytest.raises(ObsidianMcpToolError) as exc:
        read_file(cfg, path="big.txt")
    assert exc.value.code == "file_exceeds_size_cap"


def test_pdf_wrapper_and_docx_reader(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    pdf = vault / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4 placeholder")
    docx = vault / "sample.docx"
    from docx import Document

    document = Document()
    document.add_paragraph("Docx procurement conduit text")
    document.save(str(docx))
    cfg_path = _write_config(tmp_path, vault)
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg_path))
    cfg = load_config()

    class FakePdfParser:
        def parse(self, path: Path, max_chars: int = 8000) -> dict[str, Any]:
            return {
                "text_excerpt": "PDF conduit text",
                "char_count": 16,
                "page_count": 1,
                "extraction_engine": "fake",
            }

    monkeypatch.setattr("hb_assistant.obsidian_mcp.tools.PDFParser", FakePdfParser)
    assert read_file(cfg, path="sample.pdf")["content"] == "PDF conduit text"
    assert "Docx procurement" in read_file(cfg, path="sample.docx")["content"]


def test_search_respects_result_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    for idx in range(3):
        (vault / f"note-{idx}.md").write_text("conduit " * 20, encoding="utf-8")
    monkeypatch.setenv("HB_PA_CONFIG", str(_write_config(tmp_path, vault)))
    cfg = load_config().model_copy(update={"max_result_chars": 20})
    results = search_vault(cfg, query="conduit", limit=3)
    assert len(results["results"]) == 3
    assert sum(len(item.get("snippet", "")) for item in results["results"]) <= 20
