"""Schedule import package manifest for evidence locking."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _detect_type(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    if ext in {"xer", "xml", "zip", "csv"}:
        return ext
    return "unknown"


def _likely_schedule_format(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".xer"):
        return "xer"
    if lower.endswith(".xml"):
        return "xml"
    if lower.endswith(".html") or lower.endswith(".htm"):
        return "html_companion"
    if lower.endswith(".csv"):
        return "csv"
    return "unknown"


def _classify_zip_member(name: str, members: list[dict[str, Any]]) -> str:
    fmt = _likely_schedule_format(name)
    if fmt == "xer":
        xers = [m for m in members if m["likely_schedule_format"] == "xer"]
        if len(xers) == 1 and xers[0]["path"] == name:
            return "primary_candidate"
        return "companion"
    if fmt == "xml":
        xmls = [m for m in members if m["likely_schedule_format"] == "xml"]
        if len(xmls) == 1 and xmls[0]["path"] == name:
            return "primary_candidate"
        return "companion"
    if fmt == "html_companion":
        return "companion"
    if name.startswith("__MACOSX/") or name.endswith("/"):
        return "ignored"
    return "unknown"


def build_package_manifest(package_path: str | Path) -> dict[str, Any]:
    path = Path(package_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"package not found: {path}")
    pkg_type = _detect_type(path)
    out: dict[str, Any] = {
        "mode": "schedule_import_package_manifest",
        "absolute_path": str(path),
        "filename": path.name,
        "file_size": path.stat().st_size,
        "sha256": _sha256(path),
        "extension": path.suffix.lower().lstrip("."),
        "detected_package_type": pkg_type,
        "zip_members": [],
    }
    if pkg_type == "zip":
        members: list[dict[str, Any]] = []
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                members.append(
                    {
                        "path": info.filename,
                        "size": info.file_size,
                        "extension": Path(info.filename).suffix.lower().lstrip("."),
                        "likely_schedule_format": _likely_schedule_format(info.filename),
                        "role": "pending",
                    }
                )
        for member in members:
            member["role"] = _classify_zip_member(member["path"], members)
        out["zip_members"] = members
    return out


def render_package_manifest_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        "# Schedule import package manifest",
        "",
        f"- filename: `{manifest.get('filename')}`",
        f"- sha256: `{manifest.get('sha256')}`",
        f"- type: `{manifest.get('detected_package_type')}`",
        "",
    ]
    for member in manifest.get("zip_members", []):
        lines.append(
            f"- `{member['path']}` size={member['size']} role={member['role']} fmt={member['likely_schedule_format']}"
        )
    lines.append("")
    return "\n".join(lines)


def write_package_manifest_outputs(
    manifest: dict[str, Any],
    *,
    json_out: str | Path | None = None,
    md_out: str | Path | None = None,
) -> None:
    if json_out:
        Path(json_out).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if md_out:
        Path(md_out).write_text(render_package_manifest_markdown(manifest), encoding="utf-8")
