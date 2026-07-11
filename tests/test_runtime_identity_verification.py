"""Runtime identity verification — F-002 remediation (PR-2) + RT-01 attestation gates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _clear_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "HB_RUNTIME_COMMIT",
        "HB_BUILD_SHA",
        "HB_BUILD_COMMIT_VERIFIED",
        "HB_BUILD_IMAGE_DIGEST",
        "HB_BUILD_TIMESTAMP",
    ):
        monkeypatch.delenv(key, raising=False)


def test_runtime_identity_unverified_stamp_when_sha_without_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hb_assistant.nas_mcp.broker import runtime_identity
    from hb_assistant.obsidian_mcp.tool_metadata_types import RuntimeIdentityKind

    monkeypatch.setenv("HB_BUILD_SHA", "f565b19b1525fbeef75077c53be2b3bb0520c274")

    ident = runtime_identity()
    assert ident.runtime_commit == "f565b19b1525fbeef75077c53be2b3bb0520c274"
    assert ident.runtime_identity_kind == RuntimeIdentityKind.EXACT_UNVERIFIED_STAMP
    assert ident.runtime_identity_verified is False


def test_runtime_identity_unverified_when_verified_flag_without_digest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from hb_assistant.nas_mcp import build_manifest as bm
    from hb_assistant.nas_mcp.broker import runtime_identity
    from hb_assistant.obsidian_mcp.tool_metadata_types import RuntimeIdentityKind

    manifest_path = tmp_path / ".hb-build-manifest.json"
    manifest_path.write_text(json.dumps({"context_clean": True}), encoding="utf-8")
    monkeypatch.setattr(bm, "_DEFAULT_MANIFEST_PATH", manifest_path)
    monkeypatch.setenv("HB_RUNTIME_COMMIT", "a3bf1f57d2fb2ffefc8837cab2801622d71adff3")
    monkeypatch.setenv("HB_BUILD_COMMIT_VERIFIED", "1")

    ident = runtime_identity()
    assert ident.runtime_identity_kind == RuntimeIdentityKind.EXACT_UNVERIFIED_STAMP
    assert ident.runtime_identity_verified is False


def test_runtime_identity_verified_commit_requires_digest_and_clean_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from hb_assistant.nas_mcp import build_manifest as bm
    from hb_assistant.nas_mcp.broker import runtime_identity
    from hb_assistant.obsidian_mcp.tool_metadata_types import RuntimeIdentityKind

    manifest_path = tmp_path / ".hb-build-manifest.json"
    manifest_path.write_text(
        json.dumps({"context_clean": True, "context_method": "git_archive"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(bm, "_DEFAULT_MANIFEST_PATH", manifest_path)
    monkeypatch.setenv("HB_RUNTIME_COMMIT", "a3bf1f57d2fb2ffefc8837cab2801622d71adff3")
    monkeypatch.setenv("HB_BUILD_COMMIT_VERIFIED", "1")
    monkeypatch.setenv(
        "HB_BUILD_IMAGE_DIGEST",
        "sha256:" + "a" * 64,
    )
    monkeypatch.setenv("HB_BUILD_TIMESTAMP", "2026-07-10T14:00:00Z")

    ident = runtime_identity()
    assert ident.runtime_identity_kind == RuntimeIdentityKind.EXACT_VERIFIED_COMMIT
    assert ident.runtime_identity_verified is True
    assert ident.runtime_image_digest == "sha256:" + "a" * 64
    assert ident.runtime_build_timestamp == "2026-07-10T14:00:00Z"


def test_runtime_identity_prefers_runtime_commit_over_build_sha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hb_assistant.nas_mcp.broker import runtime_identity

    monkeypatch.setenv("HB_RUNTIME_COMMIT", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    monkeypatch.setenv("HB_BUILD_SHA", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")

    ident = runtime_identity()
    assert ident.runtime_commit == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def test_assistant_client_exposure_status_unverified_without_full_attestation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hb_assistant.nas_mcp.broker import assistant_client_exposure_status

    monkeypatch.setenv("HB_BUILD_SHA", "4e56e753800c045aa2311289a9b5c46360db8f3a")
    monkeypatch.setenv("HB_BUILD_COMMIT_VERIFIED", "1")

    status = assistant_client_exposure_status()
    assert status["runtime_identity_kind"] == "exact_unverified_stamp"
    assert status["runtime_identity_verified"] is False
    assert status["generated_from_runtime_commit"] == "4e56e753800c045aa2311289a9b5c46360db8f3a"


def test_dockerfile_bakes_build_provenance_env() -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "deploy" / "nas" / "Dockerfile").read_text()
    assert "ARG HB_BUILD_SHA=" in text
    assert "ENV HB_BUILD_SHA=${HB_BUILD_SHA}" in text
    assert "HB_BUILD_COMMIT_VERIFIED" in text
    assert "org.opencontainers.image.revision" in text