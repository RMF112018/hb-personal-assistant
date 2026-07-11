"""NAS image build manifest — proves clean-context builds (RT-01 Tier B)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_DEFAULT_MANIFEST_PATH = Path("/app/.hb-build-manifest.json")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$", re.IGNORECASE)


def read_build_manifest(path: Path | None = None) -> dict[str, Any]:
    """Load baked build manifest; empty dict when absent or unreadable."""
    target = path or _DEFAULT_MANIFEST_PATH
    if not target.is_file():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def build_context_clean(manifest: dict[str, Any] | None = None) -> bool:
    return bool((manifest or read_build_manifest()).get("context_clean"))


def image_digest_valid(digest: str | None) -> bool:
    return bool(digest and _DIGEST_RE.match(digest.strip()))


def commit_identity_verified(
    *,
    verified_flag: bool,
    image_digest: str | None,
    manifest: dict[str, Any] | None = None,
) -> bool:
    """True only when full commit↔image attestation gates pass (RT-01 Tier C path)."""
    if not verified_flag:
        return False
    if not image_digest_valid(image_digest):
        return False
    return build_context_clean(manifest)