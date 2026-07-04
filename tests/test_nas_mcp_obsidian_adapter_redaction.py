"""Redaction proof for the NAS obsidian adapter's host-path scrubber.

The service root moved from ``/volume1/personal-assistant`` to
``/volume2/personal-assistant`` (N8 path migration). The redactor was
generalized from a ``/volume1``-only pattern to ``/volume\\d+/`` so it scrubs
*any* NAS volume host path — the new service root, the legacy one, and the
``/volume1/homes`` source roots — before a tool response can leak it.
"""

from __future__ import annotations

from hb_assistant.nas_mcp import obsidian_adapter as adapter


def test_host_path_re_matches_any_volume() -> None:
    for host in (
        "/volume2/personal-assistant/app-support/db/x.sqlite",
        "/volume1/personal-assistant/app-support/db/x.sqlite",
        "/volume1/homes/bfetting/Work/report.pdf",
    ):
        assert adapter._HOST_PATH_RE.search(host) is not None


def test_normalize_redacts_volume2_service_root() -> None:
    payload = {
        "note": "saved to /volume2/personal-assistant/vault/obsidian/note.md",
    }
    out = adapter._normalize(payload)
    assert "/volume2/" not in out["note"]
    assert "[REDACTED_HOST_PATH]" in out["note"]


def test_normalize_redacts_legacy_and_source_root_paths() -> None:
    out = adapter._normalize(
        [
            "/volume1/personal-assistant/legacy.md",
            "/volume1/homes/bfetting/Home/a.md",
        ]
    )
    assert all("/volume" not in item for item in out)
    assert all(item == "[REDACTED_HOST_PATH]" for item in out)


def test_normalize_preserves_non_host_strings() -> None:
    out = adapter._normalize({"path_display": "vault/ok.md", "size": 42})
    assert out["path_display"] == "vault/ok.md"
    assert out["size"] == 42
