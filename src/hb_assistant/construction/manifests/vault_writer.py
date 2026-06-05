"""Marker-bounded vault writer for construction-agent projections.

Targets a construction-vault root distinct from the daily-brief vault. The
root is resolved (in precedence order) from:

1. an explicit ``vault_root`` ctor argument
2. the ``HB_CONSTRUCTION_VAULT_ROOT`` environment variable
3. ``AppConfig.paths.construction_vault_root`` (optional config field)

When none of the above is set, apply-mode writes raise
:class:`VaultRootNotConfigured`. Dry-run callers can compute paths only if
the root is configured; otherwise they should call :meth:`bootstrap_folders`
with ``dry_run=True`` to enumerate the *planned* structure (no root needed).

Writes are atomic (write-to-temp + ``os.replace``) and marker-bounded so
re-runs replace only the kind-scoped block. Any user text outside the
markers is preserved verbatim.
"""

from __future__ import annotations

import contextlib
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

ENV_VAR = "HB_CONSTRUCTION_VAULT_ROOT"

# Subdirectories under the construction vault root. Ordered by purpose.
_SUBDIRS: dict[str, str] = {
    "registry_overview": "00_Registry",
    "project_card": "01_Projects",
    "review_required": "02_Review_Queue",
    "document_card": "03_Document_Cards",
    "source_manifest": "10_Source_Manifests",
    "sync_receipt": "11_Sync_Receipts",
    "processing_receipt": "12_Processing_Receipts",
}

_MARKERS: dict[str, tuple[str, str]] = {
    "source_manifest": (
        "<!-- HB-CONSTRUCTION-MANIFEST:START -->",
        "<!-- HB-CONSTRUCTION-MANIFEST:END -->",
    ),
    "sync_receipt": (
        "<!-- HB-CONSTRUCTION-SYNC:START -->",
        "<!-- HB-CONSTRUCTION-SYNC:END -->",
    ),
    "processing_receipt": (
        "<!-- HB-CONSTRUCTION-PROCESSING:START -->",
        "<!-- HB-CONSTRUCTION-PROCESSING:END -->",
    ),
    "registry_overview": (
        "<!-- HB-CONSTRUCTION-REGISTRY:START -->",
        "<!-- HB-CONSTRUCTION-REGISTRY:END -->",
    ),
    "project_card": (
        "<!-- HB-CONSTRUCTION-PROJECT-CARD:START -->",
        "<!-- HB-CONSTRUCTION-PROJECT-CARD:END -->",
    ),
    "review_required": (
        "<!-- HB-CONSTRUCTION-REVIEW:START -->",
        "<!-- HB-CONSTRUCTION-REVIEW:END -->",
    ),
    "document_card": (
        "<!-- HB-CONSTRUCTION-DOC-CARD:START -->",
        "<!-- HB-CONSTRUCTION-DOC-CARD:END -->",
    ),
    # Procore hybrid artifact markers (for .procore-*.md files in 01_Projects/ under hybrid layout).
    # Enables write_procore_artifact to reuse _write + atomic + marker logic.
    "procore_project_card": (
        "<!-- HB-PROCORE-PROJECT-CARD:START -->",
        "<!-- HB-PROCORE-PROJECT-CARD:END -->",
    ),
    "procore_rfi_register": (
        "<!-- HB-PROCORE-RFI-REGISTER:START -->",
        "<!-- HB-PROCORE-RFI-REGISTER:END -->",
    ),
    "procore_submittal_register": (
        "<!-- HB-PROCORE-SUBMITTAL-REGISTER:START -->",
        "<!-- HB-PROCORE-SUBMITTAL-REGISTER:END -->",
    ),
    "procore_daily_log_index": (
        "<!-- HB-PROCORE-DAILY-LOG:START -->",
        "<!-- HB-PROCORE-DAILY-LOG:END -->",
    ),
    "procore_financial_snapshot": (
        "<!-- HB-PROCORE-FINANCIAL-SNAPSHOT:START -->",
        "<!-- HB-PROCORE-FINANCIAL-SNAPSHOT:END -->",
    ),
    "procore_sync_receipt": (
        "<!-- HB-PROCORE-SYNC-RECEIPT:START -->",
        "<!-- HB-PROCORE-SYNC-RECEIPT:END -->",
    ),
    "procore_endpoint_audit": (
        "<!-- HB-PROCORE-ENDPOINT-AUDIT:START -->",
        "<!-- HB-PROCORE-ENDPOINT-AUDIT:END -->",
    ),
}

_SAFE_ITEM_ID = re.compile(r"[^A-Za-z0-9_.-]+")


class VaultRootNotConfigured(RuntimeError):
    """Raised when apply mode runs without a construction vault root configured."""


@dataclass
class WriteResult:
    kind: str
    path: Path
    bytes_written: int


@dataclass
class BootstrapResult:
    subdir: str
    path: Path
    existed_before: bool
    created: bool


def _date_str(iso: str | None) -> str:
    if not iso:
        return datetime.utcnow().strftime("%Y-%m-%d")
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return datetime.utcnow().strftime("%Y-%m-%d")


def _short_run(run_id: str) -> str:
    return run_id[:8]


def _safe_item_id(item_id: str) -> str:
    return _SAFE_ITEM_ID.sub("_", item_id)[:120]


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


def _atomic_write_text(target: Path, content: str) -> int:
    """Atomically write ``content`` to ``target`` (POSIX ``os.replace`` semantics)."""

    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, target)
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            tmp_path.unlink()
        raise
    return len(content.encode("utf-8"))


def _resolve_root_from_config() -> Optional[str]:
    """Return ``AppConfig.paths.construction_vault_root`` if set, else ``None``."""

    try:
        from hb_assistant.config.loader import load_config  # local import to avoid cycle
    except Exception:
        return None
    try:
        cfg = load_config()
        return getattr(cfg.paths, "construction_vault_root", None)
    except Exception:
        return None


class ConstructionVaultWriter:
    """Writes construction-agent Markdown projections under a configured vault root."""

    def __init__(self, vault_root: str | Path | None = None) -> None:
        if vault_root is not None:
            resolved: Optional[Path] = Path(vault_root).expanduser()
        else:
            env = os.environ.get(ENV_VAR)
            if env:
                resolved = Path(env).expanduser()
            else:
                cfg_root = _resolve_root_from_config()
                resolved = Path(cfg_root).expanduser() if cfg_root else None
        self._root = resolved

    @property
    def configured(self) -> bool:
        return self._root is not None

    @property
    def root(self) -> Path:
        return self._root_or_raise()

    def _root_or_raise(self) -> Path:
        if self._root is None:
            raise VaultRootNotConfigured(
                "Construction vault root not configured. "
                f"Set the {ENV_VAR} environment variable or "
                "AppConfig.paths.construction_vault_root to enable apply writes."
            )
        return self._root

    # --- folder bootstrap -------------------------------------------------

    def planned_subdirs(self) -> list[tuple[str, str]]:
        """Return the canonical (kind, subdir) list (root-agnostic)."""

        return list(_SUBDIRS.items())

    def bootstrap_folders(self, *, dry_run: bool = False) -> list[BootstrapResult]:
        """Create (or plan) the 7 canonical construction-vault subdirectories."""

        root = self._root_or_raise()
        results: list[BootstrapResult] = []
        for _kind, subdir in _SUBDIRS.items():
            path = root / subdir
            existed = path.exists()
            created = False
            if not dry_run and not existed:
                path.mkdir(parents=True, exist_ok=True)
                created = True
            results.append(
                BootstrapResult(
                    subdir=subdir,
                    path=path,
                    existed_before=existed,
                    created=created,
                )
            )
        return results

    # --- paths ------------------------------------------------------------

    def manifest_path(self, source_key: str) -> Path:
        return self._root_or_raise() / _SUBDIRS["source_manifest"] / f"{source_key}.manifest.md"

    def sync_path(self, *, source_key: str, run_id: str, started_at: str | None) -> Path:
        return (
            self._root_or_raise()
            / _SUBDIRS["sync_receipt"]
            / f"{_date_str(started_at)}__{_short_run(run_id)}__{source_key}.sync.md"
        )

    def processing_path(self, *, run_id: str, started_at: str | None) -> Path:
        return (
            self._root_or_raise()
            / _SUBDIRS["processing_receipt"]
            / f"{_date_str(started_at)}__{_short_run(run_id)}.processing.md"
        )

    def registry_overview_path(self) -> Path:
        return self._root_or_raise() / _SUBDIRS["registry_overview"] / "registry-overview.md"

    def project_card_path(self, project_key: str) -> Path:
        return self._root_or_raise() / _SUBDIRS["project_card"] / f"{project_key}.project.md"

    def review_required_path(self, *, generated_at: str | None) -> Path:
        return (
            self._root_or_raise()
            / _SUBDIRS["review_required"]
            / f"{_date_str(generated_at)}__review-required.md"
        )

    def document_card_path(self, *, source_key: str, item_id: str) -> Path:
        return (
            self._root_or_raise()
            / _SUBDIRS["document_card"]
            / f"{source_key}__{_safe_item_id(item_id)}.doc.md"
        )

    # --- procore hybrid paths (additive; for Prompt 10 obsidian artifacts in 01_Projects/) ---

    def procore_project_artifact_path(self, project_key: str, kind: str) -> Path:
        """Return path under 01_Projects/ using hybrid filename: {project_key}.procore-{kind}.md

        kind examples: 'project-card', 'rfi-register', 'submittal-register', 'financial-snapshot' etc.
        Reuses _SUBDIRS['project_card'] and _safe_item_id.
        """
        safe_key = _safe_item_id(project_key)
        fn_kind = kind.replace("_", "-")
        return self._root_or_raise() / _SUBDIRS["project_card"] / f"{safe_key}.procore-{fn_kind}.md"

    def procore_review_required_path(self, *, generated_at: str | None) -> Path:
        """Procore review path delegate (reuses existing review_required_path for now)."""
        return self.review_required_path(generated_at=generated_at)

    # --- write methods ----------------------------------------------------

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

    def write_registry_overview(self, *, rendered: str) -> WriteResult:
        return self._write("registry_overview", self.registry_overview_path(), rendered)

    def write_project_card(self, *, project_key: str, rendered: str) -> WriteResult:
        return self._write("project_card", self.project_card_path(project_key), rendered)

    def write_review_required_note(
        self,
        *,
        generated_at: str | None,
        rendered: str,
    ) -> WriteResult:
        return self._write(
            "review_required",
            self.review_required_path(generated_at=generated_at),
            rendered,
        )

    def write_document_card(
        self,
        *,
        source_key: str,
        item_id: str,
        rendered: str,
    ) -> WriteResult:
        return self._write(
            "document_card",
            self.document_card_path(source_key=source_key, item_id=item_id),
            rendered,
        )

    # --- procore write methods (additive; delegate to _write for hybrid + reuse atomic/markers) ---

    def write_procore_artifact(self, *, project_key: str, kind: str, rendered: str) -> WriteResult:
        """Marker-bounded write for procore-* hybrid artifact in 01_Projects/.

        Maps kind -> procore_{kind} marker entry + calls _write (reuses atomic, ensure, replace).
        """
        marker_key = f"procore_{kind.replace('-', '_')}"
        target = self.procore_project_artifact_path(project_key, kind)
        return self._write(marker_key, target, rendered)

    def write_procore_review_required_note(
        self, *, generated_at: str | None, rendered: str
    ) -> WriteResult:
        """Delegate to existing review write (for procore review notes routed to 02_Review_Queue)."""
        return self.write_review_required_note(generated_at=generated_at, rendered=rendered)

    # --- private ----------------------------------------------------------

    def _write(self, kind: str, target: Path, rendered: str) -> WriteResult:
        start, end = _MARKERS[kind]
        target.parent.mkdir(parents=True, exist_ok=True)
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        framed = _ensure_markers(existing, start, end)
        new_content = _replace_bounded(framed, rendered.strip(), start, end)
        bytes_written = _atomic_write_text(target, new_content)
        return WriteResult(kind=kind, path=target, bytes_written=bytes_written)
