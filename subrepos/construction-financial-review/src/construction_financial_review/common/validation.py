"""Generic validation helpers shared by the crosswalk validator and package checks."""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Iterable

from .io import jsonl_parses, read_json


def all_files_parse(paths: Iterable[str | Path]) -> "OrderedDict":
    """Confirm every .json parses and every .jsonl line parses."""
    results = OrderedDict()
    all_ok = True
    for p in paths:
        p = Path(p)
        try:
            if p.suffix == ".jsonl":
                ok = jsonl_parses(p)
            elif p.suffix == ".json":
                read_json(p)
                ok = True
            else:
                ok = True
            results[str(p)] = ok
            all_ok = all_ok and (ok is True)
        except Exception as e:  # pragma: no cover - defensive
            results[str(p)] = f"INVALID: {e}"
            all_ok = False
    results["_all_passed"] = all_ok
    return results


def require_fields(row: dict, fields: Iterable[str]) -> list:
    """Return the list of required fields missing from a row."""
    return [f for f in fields if f not in row]
