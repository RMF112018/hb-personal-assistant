"""N8C-24 — ZIP payload safety (no traversal/absolute/encrypted/symlink/bomb; never extracts)."""

from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path

import pytest

from hb_assistant.nas_mcp.client_output_zip import ZipValidationError, validate_zip_payload
from tests.n8c24_helpers import good_zip_b64, make_env, zip_b64_with_member


def _cfg(tmp_path: Path):
    return make_env(tmp_path)["config"]


def _b(b64: str) -> bytes:
    return base64.b64decode(b64)


def test_normal_zip_accepted(tmp_path: Path) -> None:
    summary = validate_zip_payload(_cfg(tmp_path), _b(good_zip_b64()))
    assert summary["zip_validation_passed"] is True
    assert summary["member_count"] == 2 and summary["member_preview"]


@pytest.mark.parametrize("member", ["../evil.txt", "/abs/evil.txt", "a/../../etc/passwd", "run.sh"])
def test_unsafe_members_rejected(tmp_path: Path, member) -> None:
    with pytest.raises(ZipValidationError):
        validate_zip_payload(_cfg(tmp_path), _b(zip_b64_with_member(member)))


def test_too_many_members_rejected(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    object.__setattr__(cfg, "max_client_output_zip_members", 2)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i in range(5):
            z.writestr(f"f{i}.txt", "x")
    with pytest.raises(ZipValidationError, match="member count"):
        validate_zip_payload(cfg, buf.getvalue())


def test_uncompressed_bomb_rejected(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    object.__setattr__(cfg, "max_client_output_zip_uncompressed_bytes", 10)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("big.txt", "A" * 10_000)
    with pytest.raises(ZipValidationError, match="uncompressed size"):
        validate_zip_payload(cfg, buf.getvalue())


def test_bad_zip_bytes_rejected(tmp_path: Path) -> None:
    with pytest.raises(ZipValidationError, match="not a valid zip"):
        validate_zip_payload(_cfg(tmp_path), b"not a zip at all")


def test_no_extract_api_exists() -> None:
    import hb_assistant.nas_mcp.client_output_zip as mod
    assert not any("extract" in name for name in dir(mod))
