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
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import plistlib
import resource
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

_MIB = 1024 * 1024
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(_REPO_ROOT), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _filesystem_identity(path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        ["df", "-P", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    fields = completed.stdout.strip().splitlines()[-1].split()
    identity: dict[str, Any] = {
        "df_device": fields[0],
        "mount_point": fields[-1],
    }
    if sys.platform == "darwin":
        diskutil = subprocess.run(
            ["diskutil", "info", "-plist", fields[-1]],
            check=True,
            capture_output=True,
        )
        details = plistlib.loads(diskutil.stdout)
        for source, target in (
            ("FilesystemType", "filesystem_type"),
            ("FilesystemName", "filesystem_name"),
            ("DeviceIdentifier", "device_identifier"),
            ("Internal", "internal"),
            ("SolidState", "solid_state"),
            ("Encryption", "encrypted"),
            ("VolumeUUID", "volume_uuid"),
        ):
            if source in details:
                identity[target] = details[source]
    else:
        fs_type = subprocess.run(
            ["stat", "-f", "-c", "%T", str(path)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        identity["filesystem_type"] = fs_type
    return identity


def _execution_identity(
    *,
    expected_head: str | None,
    require_clean: bool,
    workdir: str | None,
) -> dict[str, Any]:
    head = _git("rev-parse", "HEAD")
    if expected_head and head != expected_head:
        raise RuntimeError(f"expected HEAD {expected_head}, observed {head}")
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    if require_clean and status:
        raise RuntimeError("exact-head evidence requires a clean worktree")

    dependency_files = [
        path
        for path in (
            _REPO_ROOT / "pyproject.toml",
            _REPO_ROOT / "uv.lock",
            _REPO_ROOT / "subrepos/construction-financial-review/pyproject.toml",
            _REPO_ROOT / "subrepos/construction-financial-review/uv.lock",
        )
        if path.is_file()
    ]
    distributions = sorted(
        {
            f"{dist.metadata.get('Name', 'unknown')}=={dist.version}"
            for dist in importlib.metadata.distributions()
        },
        key=str.casefold,
    )
    scratch_parent = Path(workdir).resolve() if workdir else Path(tempfile.gettempdir()).resolve()
    statvfs = os.statvfs(scratch_parent)
    with sqlite3.connect(":memory:") as conn:
        sqlite_compile_options = sorted(
            str(row[0]) for row in conn.execute("PRAGMA compile_options").fetchall()
        )
    return {
        "repository": {
            "root": str(_REPO_ROOT),
            "remote_origin": _git("remote", "get-url", "origin"),
            "branch": _git("branch", "--show-current"),
            "head_sha": head,
            "head_tree_sha": _git("rev-parse", "HEAD^{tree}"),
            "base_sha": _git("merge-base", "HEAD", "origin/main"),
            "worktree_clean": not bool(status),
            "worktree_status_sha256": hashlib.sha256(status.encode()).hexdigest(),
        },
        "command": {
            "cwd": str(Path.cwd().resolve()),
            "executable": sys.executable,
            "argv": list(sys.orig_argv),
            "environment": {
                key: os.environ.get(key)
                for key in ("PYTHONPATH", "PYTHONHASHSEED", "LANG", "LC_ALL", "VIRTUAL_ENV")
                if os.environ.get(key) is not None
            },
        },
        "script": {
            "path": str(Path(__file__).resolve().relative_to(_REPO_ROOT)),
            "sha256": _sha256_path(Path(__file__).resolve()),
        },
        "dependencies": {
            "identity_files": {
                str(path.relative_to(_REPO_ROOT)): {
                    "bytes": path.stat().st_size,
                    "sha256": _sha256_path(path),
                }
                for path in dependency_files
            },
            "installed_distributions": distributions,
            "installed_distributions_sha256": hashlib.sha256(
                "\n".join(distributions).encode()
            ).hexdigest(),
        },
        "runtime": {
            "python": sys.version,
            "python_implementation": platform.python_implementation(),
            "sqlite": sqlite3.sqlite_version,
            "sqlite_compile_options": sqlite_compile_options,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
        },
        "storage": {
            "scratch_parent": str(scratch_parent),
            **_filesystem_identity(scratch_parent),
            "device_id": scratch_parent.stat().st_dev,
            "block_size": statvfs.f_bsize,
            "fragment_size": statvfs.f_frsize,
            "total_bytes": statvfs.f_blocks * statvfs.f_frsize,
            "available_bytes": statvfs.f_bavail * statvfs.f_frsize,
        },
    }


def _write_evidence_bundle(
    *,
    result: dict[str, Any],
    json_out: Path,
    manifest_out: Path,
    execution_identity: dict[str, Any],
    process_exit_code: int,
) -> dict[str, Any]:
    result["execution_identity"] = execution_identity
    result["process_exit_code"] = process_exit_code
    rendered = json.dumps(result, indent=2, sort_keys=True)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(f"{rendered}\n", encoding="utf-8")
    evidence_sha256 = _sha256_path(json_out)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "artifact_type": "source_index_phase_d_exact_head_evidence_manifest",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "execution_identity": execution_identity,
        "configuration": result["configuration"],
        "slos": result["slos"],
        "started_at": result["started_at"],
        "finished_at": result["finished_at"],
        "elapsed_seconds": result["elapsed_seconds"],
        "process_exit_code": process_exit_code,
        "evaluation": result["evaluation"],
        "evidence": {
            "name": json_out.name,
            "bytes": json_out.stat().st_size,
            "sha256": evidence_sha256,
        },
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    manifest["manifest_payload_sha256"] = hashlib.sha256(canonical).hexdigest()
    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    manifest_out.write_text(f"{json.dumps(manifest, indent=2, sort_keys=True)}\n", encoding="utf-8")
    return manifest


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
    with sqlite3.connect(db_path, timeout=30) as conn:
        journal_mode = str(conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]).lower()
        conn.execute("PRAGMA wal_autocheckpoint=0")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS phase_d_wal_probe "
            "(probe_id INTEGER PRIMARY KEY, payload BLOB NOT NULL)"
        )
        conn.executemany(
            "INSERT OR REPLACE INTO phase_d_wal_probe (probe_id, payload) VALUES (?, ?)",
            ((index, os.urandom(4096)) for index in range(1, 65)),
        )
        conn.commit()
        before = _wal_size(db_path)
        passive_busy, passive_log_frames, passive_checkpointed_frames = conn.execute(
            "PRAGMA wal_checkpoint(PASSIVE)"
        ).fetchone()
        truncate_busy, truncate_log_frames, truncate_checkpointed_frames = conn.execute(
            "PRAGMA wal_checkpoint(TRUNCATE)"
        ).fetchone()
        after_truncate = _wal_size(db_path)
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        conn.execute(
            "INSERT OR REPLACE INTO phase_d_wal_probe (probe_id, payload) VALUES (?, ?)",
            (65, b"post-checkpoint-recovery"),
        )
        conn.commit()
        post_checkpoint_write_read = (
            conn.execute(
                "SELECT payload FROM phase_d_wal_probe WHERE probe_id=?", (65,)
            ).fetchone()[0]
            == b"post-checkpoint-recovery"
        )
        final_busy, _, _ = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    return {
        "journal_mode": journal_mode,
        "before_bytes": before,
        "busy": int(truncate_busy),
        "log_frames": int(passive_log_frames),
        "checkpointed_frames": int(passive_checkpointed_frames),
        "passive_busy": int(passive_busy),
        "truncate_log_frames": int(truncate_log_frames),
        "truncate_checkpointed_frames": int(truncate_checkpointed_frames),
        "after_truncate_bytes": after_truncate,
        "integrity_check": integrity,
        "post_checkpoint_write_read": post_checkpoint_write_read,
        "final_checkpoint_busy": int(final_busy),
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
            result["wal_checkpoint"]["journal_mode"] == "wal"
            and result["wal_checkpoint"]["before_bytes"] >= 4096
            and result["wal_checkpoint"]["passive_busy"] == 0
            and result["wal_checkpoint"]["log_frames"] > 0
            and result["wal_checkpoint"]["checkpointed_frames"] > 0
            and result["wal_checkpoint"]["busy"] == 0
            and result["wal_checkpoint"]["after_truncate_bytes"] <= 4096
            and result["wal_checkpoint"]["integrity_check"] == "ok"
            and result["wal_checkpoint"]["post_checkpoint_write_read"]
            and result["wal_checkpoint"]["final_checkpoint_busy"] == 0
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
        _announce(f"terminal evaluation passed={result['evaluation']['passed']}")
        if keep_workdir:
            result["scratch_path"] = str(base)
    finally:
        cleanup_error = ""
        if keep_workdir:
            result["scratch_cleaned"] = False
        else:
            try:
                shutil.rmtree(base)
            except OSError as exc:
                cleanup_error = f"{type(exc).__name__}: {exc}"
            result["scratch_cleaned"] = not base.exists()
            if cleanup_error:
                result["scratch_cleanup_error"] = cleanup_error
    return result


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
        "--manifest-out",
        help="Write an immutable exact-head execution manifest for --json-out.",
    )
    parser.add_argument(
        "--expected-head",
        help="Fail before the rehearsal unless the repository is at this exact clean HEAD.",
    )
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
    if args.manifest_out and not args.json_out:
        parser.error("--json-out is required with --manifest-out")
    if args.manifest_out and not args.expected_head:
        parser.error("--expected-head is required for an exact-head evidence manifest")

    execution_identity = _execution_identity(
        expected_head=args.expected_head,
        require_clean=bool(args.manifest_out),
        workdir=args.workdir,
    )

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
    process_exit_code = 0 if result["evaluation"]["passed"] else 1
    result["execution_identity"] = execution_identity
    result["process_exit_code"] = process_exit_code
    if args.json_out and args.manifest_out:
        manifest = _write_evidence_bundle(
            result=result,
            json_out=Path(args.json_out),
            manifest_out=Path(args.manifest_out),
            execution_identity=execution_identity,
            process_exit_code=process_exit_code,
        )
        result["evidence_manifest"] = {
            "path": str(Path(args.manifest_out)),
            "manifest_payload_sha256": manifest["manifest_payload_sha256"],
        }
    elif args.json_out:
        Path(args.json_out).write_text(
            f"{json.dumps(result, indent=2, sort_keys=True)}\n",
            encoding="utf-8",
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return process_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
