"""Phase 8 — controlled, explicit forecast package resolution + chain manifest.

A small, leaf CFR utility that turns a controlled forecast package DIRECTORY into a validated,
typed identity (``ForecastPackageRef``) and records the context->analysis chain as a deterministic
manifest (``ForecastPackageChain``). It resolves ONLY explicit package paths + manifest content —
it never performs recency-based (latest-glob) discovery, and it changes no production default.

It is mode-agnostic: a context package built file-backed or DB-backed (by the Phase 6 runner) has
identical on-disk structure, so resolution is purely structure/path based.

Stdlib only; no hb_assistant, no DB, no schema. ``_LIVE_ROOT`` below is a controlled-safety guard
(refuse resolving controlled packages under the live Synology root), NOT an authoritative
environment resolver — it mirrors the generators' default root and is monkeypatched in tests.

Fail closed: every validation failure raises ``PackageResolutionError`` — never a warning or a
soft fallback.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .project_eligibility import SUPPORTED_PROJECT_KEY, eligible_projects, is_project_eligible

CHAIN_MANIFEST_SCHEMA_VERSION = 1

# Valid package kinds. The directory-name prefix is derived per project as
# ``forecast_{kind}_package_{project_key}_`` (the stamp is the remainder of the name), so any
# eligible project resolves under the same naming convention.
_VALID_PACKAGE_KINDS = frozenset({"context", "analysis"})


def _prefix(package_kind: str, project_key: str) -> str:
    return f"forecast_{package_kind}_package_{project_key}_"


# package_kind -> required on-disk members (files/dirs) that mark a structurally valid package.
_REQUIRED_MEMBERS = {
    "context": ("manifest.json", "validation_report.json", "canonical", "summaries"),
    "analysis": (
        "manifest.json",
        "validation_report.json",
        "forecast_recommendations_by_budget_code.jsonl",
    ),
}

# Controlled-safety guard only (mirrors the generators' default Synology root); NOT an
# authoritative environment resolver. Monkeypatched in tests.
_LIVE_ROOT = Path(
    "/Users/bobbyfetting/Library/CloudStorage/SynologyDrive-BFmacSync/Work/"
    "NAS - HB/Projects/2023/TWN - NAS/30_Financials/Forecasts/Data/2026-June"
)


class PackageResolutionError(RuntimeError):
    """Raised when a forecast package identity is invalid (fail closed; no soft fallback)."""


@dataclass(frozen=True)
class ForecastPackageRef:
    """An explicit, validated identity for one controlled forecast package directory."""

    project_key: str
    package_kind: str
    package_path: Path
    stamp: str
    source: str = "explicit"


@dataclass(frozen=True)
class ForecastPackageChain:
    """The context->analysis package chain for one controlled run, keyed by package_kind."""

    project_key: str
    data_root: Path
    packages: dict[str, ForecastPackageRef]


def _is_at_or_under(path: Path, root: Path) -> bool:
    rp = path.expanduser().resolve(strict=False)
    rr = root.expanduser().resolve(strict=False)
    return rp == rr or rp.is_relative_to(rr)


def package_stamp_from_name(
    package_path: Path, *, package_kind: str, project_key: str = SUPPORTED_PROJECT_KEY
) -> str:
    """Parse the stamp from a package directory name (fail closed on any mismatch)."""
    if not is_project_eligible(project_key):
        raise PackageResolutionError(
            f"project_key {project_key!r} is not eligible; allowed: {sorted(eligible_projects())}"
        )
    if package_kind not in _VALID_PACKAGE_KINDS:
        raise PackageResolutionError(
            f"unsupported package_kind {package_kind!r}; expected one of {sorted(_VALID_PACKAGE_KINDS)}"
        )
    prefix = _prefix(package_kind, project_key)
    name = Path(package_path).name
    if not name.startswith(prefix):
        raise PackageResolutionError(
            f"{package_kind} package name does not match expected prefix {prefix!r}: {name}"
        )
    stamp = name[len(prefix) :]
    if not stamp:
        raise PackageResolutionError(f"empty stamp parsed from package name: {name}")
    return stamp


def resolve_explicit_package(
    *,
    package_kind: str,
    package_path: Path,
    project_key: str = SUPPORTED_PROJECT_KEY,
    live_root: Path | None = None,
) -> ForecastPackageRef:
    """Validate an explicit package directory and return its ``ForecastPackageRef``.

    Fails closed (``PackageResolutionError``) on: wrong project key; unsupported kind; missing
    path; non-directory path; wrong name prefix; empty stamp; any missing required member; or a
    path at/under the live Synology root. Never does recency-based discovery.
    """
    if not is_project_eligible(project_key):
        raise PackageResolutionError(
            f"project_key {project_key!r} is not eligible; allowed: {sorted(eligible_projects())}"
        )
    if package_kind not in _VALID_PACKAGE_KINDS:
        raise PackageResolutionError(
            f"unsupported package_kind {package_kind!r}; expected one of {sorted(_VALID_PACKAGE_KINDS)}"
        )

    package_path = Path(package_path)
    if not package_path.exists():
        raise PackageResolutionError(f"package_path not found: {package_path}")
    if not package_path.is_dir():
        raise PackageResolutionError(f"package_path is not a directory: {package_path}")

    stamp = package_stamp_from_name(
        package_path, package_kind=package_kind, project_key=project_key
    )

    missing = [m for m in _REQUIRED_MEMBERS[package_kind] if not (package_path / m).exists()]
    if missing:
        raise PackageResolutionError(
            f"{package_kind} package is structurally invalid (missing {missing}): {package_path}"
        )

    root = live_root if live_root is not None else _LIVE_ROOT
    if _is_at_or_under(package_path, root):
        raise PackageResolutionError(
            f"package_path is at/under the live forecast root (refused): {package_path}"
        )

    return ForecastPackageRef(
        project_key=project_key,
        package_kind=package_kind,
        package_path=package_path,
        stamp=stamp,
    )


def validate_package_ref(ref: ForecastPackageRef, *, live_root: Path | None = None) -> None:
    """Re-validate an existing ref's identity + structure (fail closed)."""
    resolve_explicit_package(
        package_kind=ref.package_kind,
        package_path=ref.package_path,
        project_key=ref.project_key,
        live_root=live_root,
    )


def build_package_chain(
    *, project_key: str, data_root: Path, refs: Iterable[ForecastPackageRef]
) -> ForecastPackageChain:
    """Assemble a chain from explicit refs (fail closed on project mismatch / duplicate kind)."""
    if not is_project_eligible(project_key):
        raise PackageResolutionError(
            f"project_key {project_key!r} is not eligible; allowed: {sorted(eligible_projects())}"
        )
    packages: dict[str, ForecastPackageRef] = {}
    for ref in refs:
        if ref.project_key != project_key:
            raise PackageResolutionError(
                f"ref project_key {ref.project_key!r} != chain project_key {project_key!r}"
            )
        if ref.package_kind in packages:
            raise PackageResolutionError(f"duplicate package_kind in chain: {ref.package_kind}")
        packages[ref.package_kind] = ref
    return ForecastPackageChain(
        project_key=project_key, data_root=Path(data_root), packages=packages
    )


def _chain_to_dict(chain: ForecastPackageChain) -> dict:
    return {
        "schema_version": CHAIN_MANIFEST_SCHEMA_VERSION,
        "project_key": chain.project_key,
        "data_root": str(chain.data_root),
        "packages": {
            kind: {
                "package_kind": ref.package_kind,
                "package_path": str(ref.package_path),
                "stamp": ref.stamp,
                "source": ref.source,
            }
            for kind, ref in chain.packages.items()
        },
    }


def write_package_chain_manifest(*, chain: ForecastPackageChain, out_path: Path) -> Path:
    """Write a deterministic (sorted-key, no wall-clock) chain manifest; return its path."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(_chain_to_dict(chain), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return out_path


def read_package_chain_manifest(path: Path) -> ForecastPackageChain:
    """Read a chain manifest back into a ``ForecastPackageChain`` (fail closed on bad shape)."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != CHAIN_MANIFEST_SCHEMA_VERSION:
        raise PackageResolutionError(
            f"unsupported chain manifest schema_version: {data.get('schema_version')!r}"
        )
    for fld in ("project_key", "data_root", "packages"):
        if fld not in data:
            raise PackageResolutionError(f"chain manifest missing field: {fld}")
    project_key = data["project_key"]
    packages: dict[str, ForecastPackageRef] = {}
    for kind, p in data["packages"].items():
        packages[kind] = ForecastPackageRef(
            project_key=project_key,
            package_kind=p["package_kind"],
            package_path=Path(p["package_path"]),
            stamp=p["stamp"],
            source=p.get("source", "explicit"),
        )
    return ForecastPackageChain(
        project_key=project_key, data_root=Path(data["data_root"]), packages=packages
    )
