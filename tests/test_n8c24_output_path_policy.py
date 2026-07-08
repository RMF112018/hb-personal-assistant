"""N8C-24 — controlled output path resolution + safety."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.nas_mcp import client_output_path_resolver as r
from tests.n8c24_helpers import make_env


def _cfg(tmp_path: Path):
    return make_env(tmp_path)["config"]


@pytest.mark.parametrize("state,top", [("pending", "00 Pending"), ("final", "01 Final")])
def test_resolves_into_controlled_folders(tmp_path: Path, state, top) -> None:
    res = r.resolve_output_relative_path(output_id="OUTPUT-20260708-001", title="My File!",
                                         file_type="docx", destination_state=state,
                                         now="2026-07-08T03:00:00+00:00", config=_cfg(tmp_path))
    assert res["resolved_relative_path"] == f"{top}/2026/07/08/OUTPUT-20260708-001 - My File.docx"
    assert res["top_level"] in r.CONTROLLED_TOP_LEVEL


def test_denied_and_unsupported_extensions_rejected(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    with pytest.raises(r.OutputPathError, match="denied output extension"):
        r.validate_output_extension(cfg, "exe")
    with pytest.raises(r.OutputPathError, match="unsupported output extension"):
        r.validate_output_extension(cfg, "xyz")


def test_write_path_rejects_traversal_absolute_and_new_top_level(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    for bad in ("../escape.md", "/etc/passwd", "Secret Folder/x.md", ".obsidian/x.md"):
        with pytest.raises(Exception):  # noqa: B017 — OutputPathError/PathAccessError family
            r.resolve_output_write_path(cfg, bad)


def test_write_path_accepts_controlled_relative(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    meta = r.resolve_output_write_path(cfg, "01 Final/2026/07/08/OUTPUT-20260708-001 - ok.md")
    assert meta["root_key"] == "outputs"
    assert meta["relative_path"].startswith("01 Final/")


def test_receipt_and_manifest_paths(tmp_path: Path) -> None:
    assert r.receipt_relative_path(output_id="OUTPUT-1").startswith("99 Receipts/")
    md, js = r.manifest_relative_paths()
    assert md == "99 Manifests/client-output-manifest.md"
    assert js == "99 Manifests/client-output-manifest.json"


def test_archive_path_under_90_archive(tmp_path: Path) -> None:
    arc = r.archive_relative_path(current_relative_path="01 Final/2026/07/08/OUTPUT-1 - x.md",
                                  now="2026-07-08T03:00:00+00:00")
    assert arc.startswith("90 Archive/")
