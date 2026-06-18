"""Phase 4 — DB-backed source-row read adapter for the forecast context generator.

Default behavior is unchanged: when the DB toggle is off (the normal case), this adapter
calls the generator's existing ``read_jsonl`` and returns its rows verbatim. It does NOT
import ``hb_assistant``, resolve a DB path, open SQLite, or inspect any env beyond the
single toggle — so file-backed runs stay byte-for-byte equivalent and CFR keeps its
stdlib-only independence.

When ``HB_FORECAST_DB_BACKED_READS=1`` the adapter reads the selected v59 source-domain
rows from SQLite instead, returning the same original JSONL row dict shape (via
``raw_json``). The DB layer (schema ownership + read repositories) lives in
``hb_assistant`` and is imported LAZILY, only inside the DB-active branch. The adapter is a
source-row PROVIDER only: it preserves source-file order and never sorts — the generator
applies its own sorts immediately after loading, exactly as today.

Fail-closed in DB-backed mode (never silently fall back to files while the toggle is on):
- ``HB_FORECAST_DB_PATH`` unset/empty;
- resolved path equals the live/default DB, or path resolution fails;
- ``hb_assistant`` import fails;
- the selected source has no rows for the (project_key, source_package) pair.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Iterable

# source_name -> hb_assistant file-order read-repository function name.
_READERS = {
    "budget_details": "read_budget_details_in_file_order",
    "cost_entries": "read_cost_entries_in_file_order",
    "monthly_actuals": "read_monthly_actuals_in_file_order",
}


class ForecastDbReadError(RuntimeError):
    """Raised when DB-backed reads are active but cannot be served (fail closed)."""


def db_backed_reads_active() -> bool:
    """True only when the explicit opt-in toggle is exactly '1' (default off)."""
    return os.environ.get("HB_FORECAST_DB_BACKED_READS") == "1"


def load_forecast_source_rows(
    source_name: str,
    *,
    jsonl_path: Any,
    source_package_name: str,
    project_key: str,
    read_jsonl_fn: Callable[[Any], Iterable[dict]],
) -> list[dict]:
    """Return source rows for ``source_name`` from JSONL (default) or SQLite (toggle on).

    ``source_name`` is one of ``budget_details`` / ``cost_entries`` / ``monthly_actuals``.
    Rows are returned in source-file order; the caller applies any sorting it needs.
    """
    if not db_backed_reads_active():
        # Toggle off: identical to today — stdlib read of the JSONL file, no hb_assistant.
        return list(read_jsonl_fn(jsonl_path))
    return _read_from_db(
        source_name, project_key=project_key, source_package_name=source_package_name
    )


def _read_from_db(source_name: str, *, project_key: str, source_package_name: str) -> list[dict]:
    if source_name not in _READERS:
        raise ForecastDbReadError(f"unknown forecast source_name: {source_name!r}")

    db_path = os.environ.get("HB_FORECAST_DB_PATH")
    if not db_path:
        raise ForecastDbReadError(
            "HB_FORECAST_DB_BACKED_READS=1 but HB_FORECAST_DB_PATH is not set (fail closed)"
        )

    # Lazy import — only when DB-backed reads are explicitly active. Import failure fails closed.
    try:
        from hb_assistant.construction.forecast import source_domain_repository as repo
        from hb_assistant.construction.forecast.source_domain_engine import is_live_db_path
        from hb_assistant.store.connection import open_connection
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise ForecastDbReadError(f"hb_assistant DB read layer unavailable: {exc}") from exc

    # Refuse the live/default DB, and fail closed if the path cannot be resolved.
    if is_live_db_path(Path(db_path)):
        raise ForecastDbReadError(
            f"HB_FORECAST_DB_PATH resolves to the live/default DB (or is unresolvable): {db_path}"
        )

    reader = getattr(repo, _READERS[source_name])
    with open_connection(Path(db_path)) as conn:
        rows = reader(conn, project_key=project_key, source_package=source_package_name)

    if not rows:
        raise ForecastDbReadError(
            f"no DB rows for source={source_name} project_key={project_key} "
            f"source_package={source_package_name!r} (fail closed; no file fallback)"
        )
    return rows
