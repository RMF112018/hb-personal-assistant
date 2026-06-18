"""Read TWN cost-forecast JSONL source files for Phase 3 source-domain projection.

Reads the three canonical source files as plain JSON (one object per non-blank
line), preserving line order and exposing a 1-based ``source_row_number`` for
deterministic lineage/IDs. The original row content is never mutated — it is the
authoritative shape for DB read-parity.

This module does NOT import the construction-financial-review Python package; it
treats the package as a read-only directory of files (the same boundary Phase 2
established for ``run_reader``/``package_reader``).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

# Canonical source filenames within a TWN cost-forecast package's ``data/`` dir
# (construction-financial-review generate_forecast_context_package.py SRC_FILES).
SOURCE_FILES = {
    "budget_details": "budget_details.jsonl",
    "cost_entries": "cost_entries.jsonl",
    "monthly_actuals": "monthly_actuals_by_budget_code.jsonl",
}


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()


def package_name_of(source_package: Path) -> str:
    """Stable package identity used for lineage and deterministic IDs (dir basename)."""
    return source_package.name


def resolve_source_path(source_package: Path, filename: str) -> Path | None:
    """Locate a source file inside a package: ``<pkg>/data/<file>`` then ``<pkg>/<file>``."""
    for candidate in (source_package / "data" / filename, source_package / filename):
        if candidate.is_file():
            return candidate
    return None


def file_sha256(path: Path) -> str | None:
    """SHA-256 of the file content, or ``None`` if it cannot be read."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def resolve_source_sha256(path: Path, source_package_name: str) -> tuple[str, bool]:
    """Return ``(sha256, used_fallback)`` for a source file.

    Falls back to a deterministic ``sha256(package_name|path)`` when the file hash
    is missing/blank — NEVER package-only, so distinct paths stay distinct and two
    unhashable files never collapse to the same lineage value.
    """
    sha = file_sha256(path)
    if sha:
        return sha, False
    return _hash(f"{source_package_name}|{path}"), True


def read_rows(path: Path) -> list[dict[str, Any]]:
    """Yield ``(source_row_number, row)`` materialized as a list.

    ``source_row_number`` is 1-based over non-blank lines (projection lineage only).
    The row dict is the exact parsed JSONL object — never mutated.
    """
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        n = 0
        for line in fh:
            line = line.strip()
            if not line:
                continue
            n += 1
            obj = json.loads(line)
            rows.append({"source_row_number": n, "row": obj})
    return rows
