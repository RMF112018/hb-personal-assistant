"""Common scan orchestration wrapper (PR 1).

ONE entry point — :func:`run_scan` — that every root-scan caller (initial bootstrap, queue rebuild, full
reconciliation, watcher poll) routes through. It owns the cross-cutting concerns that were previously
missing or duplicated:

* bounded defaults resolved HERE (not at the CLI), so an unbounded caller can never launch an
  unbounded content walk by omission — only an explicit ``unbounded=True`` removes the bounds;
* the V118 durable run record: atomic single-active-run claim, throttled + failure-isolated heartbeat,
  and a terminal status (``completed`` / ``partial`` / ``failed`` / ``interrupted``);
* bounded-out interpretation → a ``partial`` result the caller maps to its own semantics;
* a REDACTED progress token (parent-hash + depth) — never an absolute host path.

Observability is failure-isolated: any lifecycle/heartbeat/emit error is swallowed and NEVER changes the
indexing result. The ONE exception is the atomic concurrency claim — if a live run already holds the
root, :func:`run_scan` returns a ``conflict`` result (the caller treats it as retryable, not fatal).
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from contextlib import suppress
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Callable

from .config import ExternalSourceRoot, ObsidianMcpConfig
from .source_index_repository import SourceIndexRepository

_logger = logging.getLogger("hb_assistant.obsidian_mcp.source_scan_runner")


def redact_rel_prefix(rel_path: str | None) -> str:
    """Stable, non-reversible location token for progress output.

    Returns ``h<8-hex of parent dir>/d<depth>`` (or ``root`` at depth 0) — enough for an operator to see
    the walk advancing, with NO raw path segment and no way to recover the absolute host path.
    """
    if not rel_path:
        return "root"
    parent = str(PurePosixPath(str(rel_path).replace("\\", "/")).parent)
    if parent in ("", "."):
        return "root"
    depth = len([seg for seg in parent.split("/") if seg])
    digest = hashlib.sha256(parent.encode("utf-8")).hexdigest()[:8]
    return f"h{digest}/d{depth}"


@dataclass
class ScanRunResult:
    """Outcome of a :func:`run_scan` call. ``conflict`` is the retryable single-active-run signal."""

    status: str  # completed | partial | failed | conflict
    conflict: bool
    run_id: str | None
    report: Any  # ScanReport | None
    error_code: str | None


def _resolve_bounds(
    config: ObsidianMcpConfig,
    unbounded: bool,
    max_files_per_pass: int | None,
    max_seconds: float | None,
) -> tuple[int | None, float | None]:
    """Bounds priority: explicit ``unbounded`` -> (None, None); else explicit caps; else config defaults.

    A caller that supplies NO cap gets the conservative config default, so a scan is never unbounded by
    omission — only a deliberate ``unbounded=True`` removes the limits.
    """
    if unbounded:
        return None, None
    mf = (
        max_files_per_pass
        if max_files_per_pass is not None
        else int(getattr(config, "source_index_bootstrap_max_files_per_pass", 25000))
    )
    ms = (
        max_seconds
        if max_seconds is not None
        else float(getattr(config, "source_index_bootstrap_max_seconds", 600.0))
    )
    return mf, ms


def run_scan(
    root: ExternalSourceRoot,
    repo: SourceIndexRepository,
    config: ObsidianMcpConfig,
    bstate: Any,  # SourceIndexBootstrapRepository
    *,
    mode: str = "bootstrap",
    unbounded: bool = False,
    max_files_per_pass: int | None = None,
    max_seconds: float | None = None,
    emit: Callable[[dict[str, Any]], None] | None = None,
) -> ScanRunResult:
    """Run one bounded, observed, resumable scan of ``root``. See module docstring."""
    from .source_indexer import scan_source_root

    max_files_per_pass, max_seconds = _resolve_bounds(
        config, unbounded, max_files_per_pass, max_seconds
    )
    run_id = uuid.uuid4().hex
    stale = float(getattr(config, "source_index_bootstrap_stale_run_seconds", 120.0))

    active = False  # do we hold a durable run record to heartbeat/finish?
    try:
        claimed = bstate.start_bootstrap_run(
            run_id, root.source_root_key, mode, stale_seconds=stale
        )
        if claimed is None:
            # Atomic enforcement (the ONE flow-affecting lifecycle op): a live run holds this root.
            return ScanRunResult("conflict", True, None, None, "active_run_conflict")
        active = True
    except Exception:  # noqa: BLE001 — lifecycle unavailable must NOT block indexing (constraint 8)
        _logger.warning(
            "source_scan.run_start_failed",
            extra={"obsidian_mcp": {"root": root.source_root_key, "mode": mode}},
        )

    def _progress(report: Any, rel_path: str, elapsed: float) -> None:
        prefix = redact_rel_prefix(rel_path)
        if active:
            with suppress(Exception):  # heartbeat is best-effort
                bstate.heartbeat_bootstrap_run(
                    run_id,
                    phase="scan",
                    current_rel_prefix=prefix,
                    files_walked=report.files_walked,
                    metadata_upserted=report.metadata_upserted,
                    files_unchanged=report.files_unchanged,
                    content_attempted=report.content_attempted,
                    content_succeeded=report.content_succeeded,
                    content_failed=report.content_failed,
                    errors_count=report.errors,
                )
        if emit is not None:
            with suppress(Exception):
                fps = (report.files_walked / elapsed) if elapsed > 0 else 0.0
                emit(
                    {
                        "root": root.source_root_key,
                        "run_id": run_id,
                        "phase": "scan",
                        "files_walked": report.files_walked,
                        "metadata_upserted": report.metadata_upserted,
                        "content_attempted": report.content_attempted,
                        "content_succeeded": report.content_succeeded,
                        "content_failed": report.content_failed,
                        "errors": report.errors,
                        "current_dir_prefix": prefix,
                        "elapsed_s": round(elapsed, 2),
                        "files_per_s": round(fps, 1),
                    }
                )

    finished = False
    try:
        report = scan_source_root(
            root,
            repo,
            config,
            max_files_per_pass=max_files_per_pass,
            max_seconds=max_seconds,
            progress=_progress,
        )
        bounded_reason = None
        if "root_not_found" in report.error_codes:
            status = "failed"
        elif report.bounded_out:
            status = "partial"
            over_files = max_files_per_pass is not None and report.indexed >= int(
                max_files_per_pass
            )
            bounded_reason = "max_files_per_pass" if over_files else "max_seconds"
        elif report.completed:
            status = "completed"
        else:  # truncated at the global scan cap — incomplete but resumable
            status = "partial"
            bounded_reason = "scan_max_files"
        if active:
            with suppress(Exception):
                bstate.finish_bootstrap_run(
                    run_id,
                    status=status,
                    bounded_reason=bounded_reason,
                    completed_metadata_walk=report.completed,
                    reconciliation_completed=report.completed,
                    current_rel_prefix=None,
                    files_walked=report.files_walked,
                    metadata_upserted=report.metadata_upserted,
                    files_unchanged=report.files_unchanged,
                    content_attempted=report.content_attempted,
                    content_succeeded=report.content_succeeded,
                    content_failed=report.content_failed,
                    errors_count=report.errors,
                )
        finished = True
        return ScanRunResult(status, False, run_id, report, None)
    except (
        Exception
    ) as exc:  # a systemic scan failure (per-file errors are absorbed inside the scan)
        code = type(exc).__name__[:64]
        if active:
            with suppress(Exception):
                bstate.finish_bootstrap_run(run_id, status="failed", last_error_code=code)
        finished = True
        return ScanRunResult("failed", False, run_id, None, code)
    finally:
        if active and not finished:
            with suppress(Exception):
                bstate.interrupt_bootstrap_run(run_id)
