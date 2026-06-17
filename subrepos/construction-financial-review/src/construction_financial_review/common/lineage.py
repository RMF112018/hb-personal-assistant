"""Shared upstream context-package resolution + lineage metadata for fresh-run consistency.

Every forecast stage that consumes the context package resolves it through `resolve_context_package`
so default resolution is uniform (latest-glob) and pin-aware. A pinned stamp (`--context-stamp`)
resolves the exact package and fails closed when missing — never a silent fallback to latest. Each
stage records the returned `lineage` dict in its `input_inventory.json` so the comprehensive package
can prove the whole run consumed one consistent context package (`full_run_lineage_consistent`).
"""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Optional

from .hashing import sha256_file
from .io import read_json

CONTEXT_PREFIX = "forecast_context_package"


def _glob(project_key: str) -> str:
    return f"{CONTEXT_PREFIX}_{project_key}_*"


def _stamp_of(pkg: Path) -> Optional[str]:
    # forecast_context_package_<project>_<YYYYmmdd_HHMMSS>
    name = pkg.name
    parts = name.split("_")
    return "_".join(parts[-2:]) if len(parts) >= 2 else None


def _latest_dir(data_root: Path, pattern: str) -> Optional[Path]:
    matches = sorted(p for p in data_root.glob(pattern) if p.is_dir())
    return matches[-1] if matches else None


def context_lineage(pkg: Optional[Path], lineage_source: str) -> "OrderedDict":
    """Build the lineage metadata recorded by every consuming stage."""
    if pkg is None:
        return OrderedDict([
            ("consumed_context_package", None), ("consumed_context_stamp", None),
            ("consumed_context_manifest_generated_at", None),
            ("consumed_context_manifest_hash", None), ("lineage_source", lineage_source)])
    manifest_path = pkg / "manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    return OrderedDict([
        ("consumed_context_package", pkg.name),
        ("consumed_context_stamp", _stamp_of(pkg)),
        ("consumed_context_manifest_generated_at",
         (manifest or {}).get("generated_timestamp_local") or (manifest or {}).get("generated_stamp")),
        ("consumed_context_manifest_hash",
         sha256_file(manifest_path) if manifest_path.exists() else None),
        ("lineage_source", lineage_source),
    ])


def resolve_context_package(data_root: Path, cfg: dict, project_key: str, *,
                            context_stamp: Optional[str] = None, strict_pin: bool = False):
    """Return (context_pkg_path, lineage_meta).

    - context_stamp given -> resolve the exact `forecast_context_package_<project>_<stamp>`; if absent
      and strict_pin, raise SystemExit (no silent fallback). lineage_source="pinned".
    - else -> latest-glob (uniform across stages; supersedes any stale configured named package).
    """
    data_root = Path(data_root)
    if context_stamp:
        pinned = data_root / f"{CONTEXT_PREFIX}_{project_key}_{context_stamp}"
        if pinned.is_dir():
            return pinned, context_lineage(pinned, "pinned")
        if strict_pin:
            raise SystemExit(
                f"ERROR: pinned context package not found: {pinned.name} under {data_root}")
        # non-strict pin miss -> fall through to latest-glob (still recorded as latest_glob)
    pkg = _latest_dir(data_root, _glob(project_key))
    return pkg, context_lineage(pkg, "latest_glob")


def pin_context_into_cfg(cfg: dict, data_root, project_key: str):
    """Resolve context (honoring a cfg pin), inject the resolved name into a cfg copy so every stage's
    existing discovery selects the same package, and return (new_cfg, context_pkg, lineage_meta).

    The pin rides in cfg as `_pinned_context_stamp` / `_strict_pin` (set by the CLI `--context-stamp`).
    """
    pkg, meta = resolve_context_package(
        Path(data_root), cfg, project_key,
        context_stamp=cfg.get("_pinned_context_stamp"), strict_pin=bool(cfg.get("_strict_pin")))
    new_cfg = dict(cfg)
    if pkg is not None:
        new_cfg["forecast_context_package"] = pkg.name
    return new_cfg, pkg, meta
