#!/usr/bin/env python3
"""Scratch-only Source Index Phase D scalability and resilience rehearsal.

The default run creates one deterministic synthetic tree, proves fresh 400,000- and
1,000,000-file metadata scans, then exercises no-change and 0.1/1/10 percent delta
generations, FTS latency/concurrency, WAL checkpointing, and bounded SQLite lock
contention. It never points at a configured source root, production database, or NAS.

Examples:
    python scripts/source_index_phase_d_rehearsal.py --json-out phase-d.json
    python scripts/source_index_phase_d_rehearsal.py --targets 2000,5000 --quick
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import resource
import shutil
import sqlite3
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

_MIB = 1024 * 1024


def _peak_rss_mb() -> float:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    divisor = _MIB if sys.platform == "darwin" else 1024
    return round(raw / divisor, 1)


def _announce(message: str) -> None:
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[phase-d {stamp}] {message}", file=sys.stderr, flush=True)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(percentile * len(ordered)) - 1))
    return round(ordered[index], 3)


def _write_small(path: Path, payload: bytes = b"x" * 64) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(fd, payload)
    finally:
        os.close(fd)


def _seed_topologies(root: Path, *, fanout_files: int, deep_levels: int) -> list[Path]:
    """Create every non-bulk topology once and return the physical files created."""
    made: list[Path] = []
    fanout = root / "high-fanout"
    fanout.mkdir(parents=True)
    for index in range(fanout_files):
        path = fanout / f"fanout-{index:05d}.txt"
        _write_small(path)
        made.append(path)

    deep = root / "deep"
    for level in range(deep_levels):
        deep /= f"level-{level:02d}"
        deep.mkdir(parents=True)
        path = deep / f"deep-{level:02d}.txt"
        _write_small(path)
        made.append(path)

    needles = root / "formats"
    needles.mkdir()
    special_payloads = {
        "phaseDneedle.txt": b"metadata-only search marker",
        "corrupt.zip": b"PK\x03\x04not-a-valid-archive",
        "corrupt.docx": b"PK\x03\x04not-a-valid-office-file",
        "corrupt.xlsx": b"PK\x03\x04not-a-valid-spreadsheet",
        "large.pdf": b"%PDF-1.7\n",
        "large.xlsx": b"PK\x03\x04",
    }
    for name, payload in special_payloads.items():
        path = needles / name
        _write_small(path, payload)
        if name.startswith("large."):
            os.truncate(path, 8 * _MIB)
        made.append(path)
    return made


def _extend_bulk(
    root: Path,
    *,
    current_count: int,
    target_count: int,
    files_per_dir: int,
) -> tuple[int, float]:
    started = time.monotonic()
    bulk_index = current_count
    while current_count < target_count:
        directory = root / "bulk" / f"d{bulk_index // files_per_dir:06d}"
        directory.mkdir(parents=True, exist_ok=True)
        in_directory = min(files_per_dir - (bulk_index % files_per_dir), target_count - current_count)
        for offset in range(in_directory):
            index = bulk_index + offset
            _write_small(directory / f"f{index:08d}.txt")
        bulk_index += in_directory
        current_count += in_directory
    return current_count, round(time.monotonic() - started, 3)


def _count_content_rows(db_path: Path) -> int:
    with sqlite3.connect(db_path) as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM source_intelligence_metadata "
                "WHERE content_indexed_at IS NOT NULL"
            ).fetchone()[0]
        )


def _wal_size(db_path: Path) -> int:
    wal = Path(f"{db_path}-wal")
    return wal.stat().st_size if wal.exists() else 0


@contextmanager
def _parser_tripwire() -> Iterator[dict[str, int]]:
    """Fail immediately if a metadata bootstrap invokes hashing or content extraction."""
    from hb_assistant.obsidian_mcp import source_indexer as si

    calls = {"hash": 0, "extract": 0}
    original_hash = si._sha256_file
    original_extract = si._extract

    def forbidden_hash(*_args: Any, **_kwargs: Any) -> str:
        calls["hash"] += 1
        raise AssertionError("metadata bootstrap invoked file hashing")

    def forbidden_extract(*_args: Any, **_kwargs: Any) -> str:
        calls["extract"] += 1
        raise AssertionError("metadata bootstrap invoked content extraction")

    si._sha256_file = forbidden_hash
    si._extract = forbidden_extract
    try:
        yield calls
    finally:
        si._sha256_file = original_hash
        si._extract = original_extract


def _configuration(root: Path, *, observed_limit: int) -> tuple[Any, Any]:
    from hb_assistant.obsidian_mcp.config import ExternalSourceRoot, ObsidianMcpConfig

    external = ExternalSourceRoot(source_root_key="phase-d", path=str(root), enabled=True)
    config = ObsidianMcpConfig(
        vault_root=str(root.parent),
        external_sources=[external],
        external_source_index_enabled=True,
        source_index_enable_synchronous_parser_extraction=False,
        source_index_metadata_batch_size=min(1000, observed_limit),
        source_index_scan_observed_files_per_pass=observed_limit,
        source_index_directory_fanout_limit=20_000,
    )
    return external, config


def _run_generation(
    root: Path,
    db_path: Path,
    *,
    observed_limit: int,
    label: str = "generation",
    pass_ceiling: int = 10_000,
) -> dict[str, Any]:
    from hb_assistant.obsidian_mcp import source_indexer as si
    from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
    from hb_assistant.store.source_index_scan_generations_repository import (
        SourceIndexScanGenerationsRepository,
    )

    external, config = _configuration(root, observed_limit=observed_limit)
    repo = SourceIndexRepository(db_path)
    started = time.monotonic()
    statuses: list[str | None] = []
    generation_id: str | None = None
    _announce(f"{label}: start")
    with _parser_tripwire() as parser_calls:
        for pass_index in range(1, pass_ceiling + 1):
            report = si.scan_source_root(external, repo, config)
            statuses.append(report.generation_status)
            generation_id = report.generation_id
            _announce(
                f"{label}: pass={pass_index} status={report.generation_status} "
                f"walked={report.files_walked} upserted={report.metadata_upserted} "
                f"unchanged={report.files_unchanged}"
            )
            if report.generation_status == "completed":
                break
            if report.generation_status in {"failed", "abandoned", "conflict"}:
                raise RuntimeError(
                    f"generation stopped in {report.generation_status}: {report.error_code}"
                )
        else:
            raise RuntimeError(f"generation exceeded {pass_ceiling} passes")
    elapsed = time.monotonic() - started
    if generation_id is None:
        raise RuntimeError("scan returned no generation identity")
    generation = SourceIndexScanGenerationsRepository(db_path).get_generation(generation_id)
    if generation is None:
        raise RuntimeError(f"generation row missing: {generation_id}")
    active = len(repo.active_rel_paths("phase-d"))
    _announce(f"{label}: completed active_rows={active} seconds={elapsed:.3f}")
    return {
        "generation_id": generation_id,
        "status": generation["status"],
        "passes": len(statuses),
        "pass_statuses": statuses,
        "seconds": round(elapsed, 3),
        "files_per_second": round(int(generation["files_observed"]) / elapsed, 1),
        "files_observed": int(generation["files_observed"]),
        "metadata_upserted": int(generation["metadata_upserted"]),
        "files_unchanged": int(generation["files_unchanged"]),
        "deleted_count": int(generation["deleted_count"]),
        "errors_count": int(generation["errors_count"]),
        "active_rows": active,
        "content_rows": _count_content_rows(db_path),
        "parser_invocations": parser_calls,
        "wal_bytes": _wal_size(db_path),
    }


def _fresh_scan(
    root: Path,
    db_path: Path,
    *,
    expected_files: int,
    observed_limit: int,
) -> dict[str, Any]:
    from hb_assistant.store.migrator import SQLiteMigrator

    SQLiteMigrator(db_path=db_path).apply()
    rss_before = _peak_rss_mb()
    result = _run_generation(
        root,
        db_path,
        observed_limit=observed_limit,
        label=f"fresh-{expected_files}",
    )
    result.update(
        {
            "expected_files": expected_files,
            "all_files_discoverable": result["active_rows"] == expected_files,
            "metadata_only": result["content_rows"] == 0,
            "bounded_resume": result["passes"] >= 2,
            "rss_before_mb": rss_before,
            "peak_rss_mb": _peak_rss_mb(),
            "db_bytes": db_path.stat().st_size,
        }
    )
    result["rss_growth_mb"] = round(result["peak_rss_mb"] - rss_before, 1)
    return result


def _bulk_paths(root: Path, start_index: int, total: int, files_per_dir: int) -> Iterator[Path]:
    for index in range(start_index, start_index + total):
        yield root / "bulk" / f"d{index // files_per_dir:06d}" / f"f{index:08d}.txt"


def _touch_delta(root: Path, start_index: int, count: int, files_per_dir: int) -> float:
    started = time.monotonic()
    stamp = time.time_ns()
    touched = 0
    for path in _bulk_paths(root, start_index, count, files_per_dir):
        if path.exists():
            os.utime(path, ns=(stamp, stamp))
            touched += 1
    if touched != count:
        raise RuntimeError(f"requested {count} delta files but touched {touched}")
    return round(time.monotonic() - started, 3)


def _search_latency(
    db_path: Path,
    *,
    workers: int,
    queries_per_worker: int,
) -> dict[str, Any]:
    from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository

    started = time.perf_counter()
    cold_results = SourceIndexRepository(db_path).search_source_files(
        "phaseDneedle", source_root_key="phase-d", limit=5
    )
    cold_ms = (time.perf_counter() - started) * 1000

    warm_repo = SourceIndexRepository(db_path)
    warm_ms: list[float] = []
    for _ in range(30):
        started = time.perf_counter()
        rows = warm_repo.search_source_files(
            "phaseDneedle", source_root_key="phase-d", limit=5
        )
        warm_ms.append((time.perf_counter() - started) * 1000)
        if not rows:
            raise RuntimeError("warm FTS query returned no result")

    def query_worker() -> tuple[list[float], int, int]:
        repo = SourceIndexRepository(db_path)
        latencies: list[float] = []
        result_count = 0
        failures = 0
        for _ in range(queries_per_worker):
            begun = time.perf_counter()
            try:
                result_count += len(
                    repo.search_source_files(
                        "phaseDneedle", source_root_key="phase-d", limit=5
                    )
                )
            except Exception:
                failures += 1
            latencies.append((time.perf_counter() - begun) * 1000)
        return latencies, result_count, failures

    concurrent_ms: list[float] = []
    concurrent_results = 0
    concurrent_failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for latencies, result_count, failures in pool.map(
            lambda _index: query_worker(), range(workers)
        ):
            concurrent_ms.extend(latencies)
            concurrent_results += result_count
            concurrent_failures += failures
    return {
        "cold_connection_ms": round(cold_ms, 3),
        "cold_result_count": len(cold_results),
        "warm_p50_ms": _percentile(warm_ms, 0.50),
        "warm_p95_ms": _percentile(warm_ms, 0.95),
        "warm_max_ms": round(max(warm_ms), 3),
        "concurrent_workers": workers,
        "concurrent_queries": workers * queries_per_worker,
        "concurrent_p95_ms": _percentile(concurrent_ms, 0.95),
        "concurrent_max_ms": round(max(concurrent_ms), 3),
        "concurrent_result_count": concurrent_results,
        "concurrent_failures": concurrent_failures,
    }


def _wal_checkpoint(db_path: Path) -> dict[str, Any]:
    before = _wal_size(db_path)
    with sqlite3.connect(db_path, timeout=30) as conn:
        busy, log_frames, checkpointed_frames = conn.execute(
            "PRAGMA wal_checkpoint(TRUNCATE)"
        ).fetchone()
    return {
        "before_bytes": before,
        "busy": int(busy),
        "log_frames": int(log_frames),
        "checkpointed_frames": int(checkpointed_frames),
        "after_bytes": _wal_size(db_path),
    }


def _lock_contention(root: Path, db_path: Path, *, observed_limit: int) -> dict[str, Any]:
    lock = sqlite3.connect(db_path, timeout=30)
    lock.execute("BEGIN IMMEDIATE")
    started = time.monotonic()
    error = ""
    try:
        try:
            _run_generation(
                root,
                db_path,
                observed_limit=observed_limit,
                label="lock-contention-attempt",
            )
        except sqlite3.OperationalError as exc:
            error = str(exc)
    finally:
        lock.rollback()
        lock.close()
    elapsed = time.monotonic() - started
    recovery = _run_generation(
        root,
        db_path,
        observed_limit=observed_limit,
        label="lock-contention-recovery",
    )
    return {
        "blocked_seconds": round(elapsed, 3),
        "bounded_lock_error": "locked" in error.lower(),
        "error": error,
        "recovery_status": recovery["status"],
        "recovery_active_rows": recovery["active_rows"],
        "recovery_generation_id": recovery["generation_id"],
    }


def _evaluate(result: dict[str, Any], slos: dict[str, float]) -> dict[str, Any]:
    max_target = max(result["scale_scans"], key=lambda value: int(value))
    million = result["scale_scans"][max_target]
    checks: dict[str, bool] = {
        "all_scale_scans_completed": all(
            scan["status"] == "completed" for scan in result["scale_scans"].values()
        ),
        "all_files_discoverable": all(
            scan["all_files_discoverable"] for scan in result["scale_scans"].values()
        ),
        "bounded_resume": all(scan["bounded_resume"] for scan in result["scale_scans"].values()),
        "metadata_only_no_parser": all(
            scan["metadata_only"]
            and scan["parser_invocations"] == {"hash": 0, "extract": 0}
            for scan in result["scale_scans"].values()
        ),
        "bounded_rss": million["peak_rss_mb"] <= slos["max_peak_rss_mb"],
        "minimum_throughput": million["files_per_second"] >= slos["min_files_per_second"],
        "no_change_fast_skip": (
            result["no_change"]["metadata_upserted"] == 0
            and result["no_change"]["files_unchanged"] == million["expected_files"]
        ),
        "delta_counts_exact": all(
            run["metadata_upserted"] == run["expected_changed"]
            and run["files_unchanged"] == million["expected_files"] - run["expected_changed"]
            for run in result["delta_scans"]
        ),
        "cold_search_slo": (
            result["search"]["cold_result_count"] > 0
            and result["search"]["cold_connection_ms"] <= slos["cold_search_ms"]
        ),
        "warm_search_slo": result["search"]["warm_p95_ms"] <= slos["warm_search_p95_ms"],
        "concurrent_read_slo": (
            result["search"]["concurrent_failures"] == 0
            and result["search"]["concurrent_p95_ms"] <= slos["concurrent_search_p95_ms"]
        ),
        "wal_checkpoint_bounded": (
            result["wal_checkpoint"]["busy"] == 0
            and result["wal_checkpoint"]["after_bytes"] <= 4096
        ),
        "lock_contention_bounded_and_recovers": (
            result["lock_contention"]["bounded_lock_error"]
            and result["lock_contention"]["blocked_seconds"] <= slos["lock_timeout_seconds"]
            and result["lock_contention"]["recovery_status"] == "completed"
        ),
    }
    return {"checks": checks, "passed": all(checks.values())}


def run_rehearsal(
    *,
    targets: list[int],
    observed_limit: int,
    files_per_dir: int,
    fanout_files: int,
    deep_levels: int,
    delta_percentages: list[float],
    workers: int,
    queries_per_worker: int,
    workdir: str | None,
    keep_workdir: bool,
    slos: dict[str, float],
) -> dict[str, Any]:
    if not targets or sorted(set(targets)) != targets or targets[0] <= 0:
        raise ValueError("targets must be unique, ascending positive integers")
    if targets[0] <= fanout_files + deep_levels + 6:
        raise ValueError("smallest target must exceed the requested topology seed")

    base = Path(tempfile.mkdtemp(prefix="source-index-phase-d-", dir=workdir))
    root = base / "synthetic-root"
    root.mkdir()
    started = time.monotonic()
    physical_files = _seed_topologies(root, fanout_files=fanout_files, deep_levels=deep_levels)
    file_count = len(physical_files)
    result: dict[str, Any] = {
        "schema_version": 1,
        "phase": "D",
        "scope": "scratch-only synthetic metadata index; no NAS, configured roots, or production DB",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "platform": sys.platform,
            "python": sys.version.split()[0],
            "cpu_count": os.cpu_count(),
        },
        "configuration": {
            "targets": targets,
            "observed_files_per_pass": observed_limit,
            "files_per_directory": files_per_dir,
            "high_fanout_files": fanout_files,
            "deep_levels": deep_levels,
            "delta_percentages": delta_percentages,
        },
        "slos": slos,
        "scale_scans": {},
        "build_steps": [],
    }
    try:
        for target in targets:
            _announce(f"building physical tree to {target} files")
            file_count, build_seconds = _extend_bulk(
                root,
                current_count=file_count,
                target_count=target,
                files_per_dir=files_per_dir,
            )
            result["build_steps"].append(
                {"target": target, "physical_files": file_count, "seconds": build_seconds}
            )
            db_path = base / f"scale-{target}.db"
            result["scale_scans"][str(target)] = _fresh_scan(
                root,
                db_path,
                expected_files=target,
                observed_limit=observed_limit,
            )

        max_target = targets[-1]
        db_path = base / f"scale-{max_target}.db"
        result["no_change"] = _run_generation(
            root,
            db_path,
            observed_limit=observed_limit,
            label="no-change",
        )
        result["delta_scans"] = []
        bulk_available = max_target - (fanout_files + deep_levels + 6)
        for percentage in delta_percentages:
            changed = max(1, round(max_target * percentage / 100))
            if changed > bulk_available:
                raise ValueError(f"delta {percentage}% exceeds available bulk files")
            touch_seconds = _touch_delta(
                root, fanout_files + deep_levels + 6, changed, files_per_dir
            )
            scan = _run_generation(
                root,
                db_path,
                observed_limit=observed_limit,
                label=f"delta-{percentage:g}-percent",
            )
            scan.update(
                {
                    "percentage": percentage,
                    "expected_changed": changed,
                    "touch_seconds": touch_seconds,
                }
            )
            result["delta_scans"].append(scan)

        _announce("measuring FTS latency and concurrent read-only queries")
        result["search"] = _search_latency(
            db_path, workers=workers, queries_per_worker=queries_per_worker
        )
        _announce("measuring WAL checkpoint")
        result["wal_checkpoint"] = _wal_checkpoint(db_path)
        _announce("measuring bounded lock contention and recovery")
        result["lock_contention"] = _lock_contention(
            root, db_path, observed_limit=observed_limit
        )
        result["evaluation"] = _evaluate(result, slos)
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        result["scratch_cleaned"] = not keep_workdir
        _announce(f"terminal evaluation passed={result['evaluation']['passed']}")
        if keep_workdir:
            result["scratch_path"] = str(base)
        return result
    finally:
        if not keep_workdir:
            shutil.rmtree(base, ignore_errors=True)


def _parse_csv_ints(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def _parse_csv_floats(value: str) -> list[float]:
    return [float(item.strip()) for item in value.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", default="400000,1000000")
    parser.add_argument("--observed-files-per-pass", type=int, default=25_000)
    parser.add_argument("--files-per-dir", type=int, default=1_000)
    parser.add_argument("--fanout-files", type=int, default=10_000)
    parser.add_argument("--deep-levels", type=int, default=32)
    parser.add_argument("--delta-percentages", default="0.1,1,10")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--queries-per-worker", type=int, default=20)
    parser.add_argument("--workdir")
    parser.add_argument("--keep-workdir", action="store_true")
    parser.add_argument("--json-out")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Use CI-safe topology/concurrency defaults; target sizes still come from --targets.",
    )
    args = parser.parse_args()
    if args.quick:
        args.fanout_files = min(args.fanout_files, 100)
        args.deep_levels = min(args.deep_levels, 8)
        args.workers = min(args.workers, 4)
        args.queries_per_worker = min(args.queries_per_worker, 5)

    slos = {
        "max_peak_rss_mb": 1024.0,
        "min_files_per_second": 500.0,
        "cold_search_ms": 5000.0,
        "warm_search_p95_ms": 250.0,
        "concurrent_search_p95_ms": 1000.0,
        "lock_timeout_seconds": 10.0,
    }
    result = run_rehearsal(
        targets=_parse_csv_ints(args.targets),
        observed_limit=args.observed_files_per_pass,
        files_per_dir=args.files_per_dir,
        fanout_files=args.fanout_files,
        deep_levels=args.deep_levels,
        delta_percentages=_parse_csv_floats(args.delta_percentages),
        workers=args.workers,
        queries_per_worker=args.queries_per_worker,
        workdir=args.workdir,
        keep_workdir=args.keep_workdir,
        slos=slos,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out:
        Path(args.json_out).write_text(f"{rendered}\n", encoding="utf-8")
    return 0 if result["evaluation"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
