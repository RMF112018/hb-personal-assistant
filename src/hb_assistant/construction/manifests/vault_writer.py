"""Marker-bounded vault writer for construction-agent projections.

Targets a construction-vault root distinct from the daily-brief vault. The
root is resolved from the ``HB_CONSTRUCTION_VAULT_ROOT`` environment variable;
when unset, ``apply`` writes raise :class:`VaultRootNotConfigured`. Dry-run
preview paths can be computed without the env var.

Each generated file is wrapped in markers so a re-run replaces only the
bounded block. Any user text outside the markers is preserved verbatim.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ENV_VAR = "HB_CONSTRUCTION_VAULT_ROOT"

_SUBDIRS = {
    "source_manifest": "10_Source_Manifests",
    "sync_receipt": "11_Sync_Receipts",
    "processing_receipt": "12_Processing_Receipts",
}

_MARKERS = {
    "source_manifest": ("<!-- HB-CONSTRUCTION-MANIFEST:START -->", "<!-- HB-CONSTRUCTION-MANIFEST:END -->"),
    "sync_receipt": ("<!-- HB-CONSTRUCTION-SYNC:START -->", "<!-- HB-CONSTRUCTION-SYNC:END -->"),
    "processing_receipt": ("<!-- HB-CONSTRUCTION-PROCESSING:START -->", "<!-- HB-CONSTRUCTION-PROCESSING:END -->"),
}


class VaultRootNotConfigured(RuntimeError):
    """Raised when apply mode runs without HB_CONSTRUCTION_VAULT_ROOT set."""


@dataclass
class WriteResult:
    kind: str
    path: Path
    bytes_written: int


def _date_str(iso: str | None) -> str:
    if not iso:
        return datetime.utcnow().strftime("%Y-%m-%d")
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return datetime.utcnow().strftime("%Y-%m-%d")


def _short_run(run_id: str) -> str:
    return run_id[:8]


def _ensure_markers(existing: str, start: str, end: str) -> str:
    if start in existing and end in existing:
        return existing
    if existing and not existing.endswith("\n"):
        existing += "\n"
    return existing + f"\n{start}\n{end}\n"


def _replace_bounded(existing: str, inner: str, start: str, end: str) -> str:
    pattern = re.compile(
        rf"({re.escape(start)})(.*?)({re.escape(end)})",
        re.DOTALL,
    )
    if pattern.search(existing):
        return pattern.sub(rf"\1\n{inner}\n\3", existing)
    return existing


class ConstructionVaultWriter:
    """Writes construction-agent Markdown projections under a configured vault root."""

    def __init__(self, vault_root: str | Path | None = None) -> None:
        if vault_root is not None:
            self._root: Path | None = Path(vault_root).expanduser()
        else:
            env = os.environ.get(ENV_VAR)
            self._root = Path(env).expanduser() if env else None

    @property
    def configured(self) -> bool:
        return self._root is not None

    def _root_or_raise(self) -> Path:
        if self._root is None:
            raise VaultRootNotConfigured(
                f"Construction vault root not configured. "
                f"Set the {ENV_VAR} environment variable to enable apply writes."
            )
        return self._root

    def manifest_path(self, source_key: str) -> Path:
        root = self._root_or_raise()
        return root / _SUBDIRS["source_manifest"] / f"{source_key}.manifest.md"

    def sync_path(self, *, source_key: str, run_id: str, started_at: str | None) -> Path:
        root = self._root_or_raise()
        return (
            root / _SUBDIRS["sync_receipt"]
            / f"{_date_str(started_at)}__{_short_run(run_id)}__{source_key}.sync.md"
        )

    def processing_path(self, *, run_id: str, started_at: str | None) -> Path:
        root = self._root_or_raise()
        return (
            root / _SUBDIRS["processing_receipt"]
            / f"{_date_str(started_at)}__{_short_run(run_id)}.processing.md"
        )

    def write_source_manifest(self, *, source_key: str, rendered: str) -> WriteResult:
        return self._write("source_manifest", self.manifest_path(source_key), rendered)

    def write_sync_receipt(
        self,
        *,
        source_key: str,
        run_id: str,
        started_at: str | None,
        rendered: str,
    ) -> WriteResult:
        return self._write(
            "sync_receipt",
            self.sync_path(source_key=source_key, run_id=run_id, started_at=started_at),
            rendered,
        )

    def write_processing_receipt(
        self,
        *,
        run_id: str,
        started_at: str | None,
        rendered: str,
    ) -> WriteResult:
        return self._write(
            "processing_receipt",
            self.processing_path(run_id=run_id, started_at=started_at),
            rendered,
        )

    def _write(self, kind: str, target: Path, rendered: str) -> WriteResult:
        start, end = _MARKERS[kind]
        target.parent.mkdir(parents=True, exist_ok=True)
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        framed = _ensure_markers(existing, start, end)
        new_content = _replace_bounded(framed, rendered.strip(), start, end)
        target.write_text(new_content, encoding="utf-8")
        return WriteResult(kind=kind, path=target, bytes_written=len(new_content.encode("utf-8")))
