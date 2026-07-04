#!/usr/bin/env python3
"""N4B benchmark-only SQLite tooling — not wired into production runtime."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

BENCH_TABLE = "__n4b_sqlite_bench_events"

FINGERPRINT_TABLES = (
    "procore_ep_budget_detail_row_cells",
    "second_brain_financial_review_required_items",
    "procore_ep_subcontractor_invoice_contract_detail_items",
    "procore_ep_budget_detail_rows",
    "forecast_cost_entries",
    "procore_ep_schedule_activities",
    "procore_ep_schedule_relationships",
    "schedule_file_imports",
    "schedule_cpm_runs",
    "schedule_cpm_activity_results",
    "schema_migrations",
)

READ_COUNT_TABLES = FINGERPRINT_TABLES

DENYLIST_PATHS = {
    Path(
        "/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"
    ).resolve(),
    Path("/volume1/personal-assistant/app-support/db/hb-personal-assistant.sqlite").resolve(),
}


@dataclass
class TimingStats:
    samples_ms: list[float] = field(default_factory=list)
    errors: int = 0
    busy_errors: int = 0

    def add(self, elapsed_ms: float) -> None:
        self.samples_ms.append(elapsed_ms)

    def add_error(self, exc: BaseException) -> None:
        self.errors += 1
        if isinstance(exc, sqlite3.OperationalError):
            msg = str(exc).lower()
            if "locked" in msg or "busy" in msg:
                self.busy_errors += 1

    def summary(self) -> dict[str, Any]:
        if not self.samples_ms:
            return {"count": 0, "errors": self.errors, "busy_errors": self.busy_errors}
        ordered = sorted(self.samples_ms)
        n = len(ordered)

        def pct(p: float) -> float:
            idx = min(n - 1, max(0, int(round(p * (n - 1)))))
            return round(ordered[idx], 3)

        return {
            "count": n,
            "p50_ms": pct(0.50),
            "p95_ms": pct(0.95),
            "p99_ms": pct(0.99),
            "max_ms": round(ordered[-1], 3),
            "errors": self.errors,
            "busy_errors": self.busy_errors,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _file_fingerprint(path: Path) -> dict[str, Any]:
    st = path.stat()
    return {
        "path": str(path),
        "size_bytes": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "ino": st.st_ino,
    }


def _is_scratch_path(resolved: Path) -> bool:
    s = str(resolved)
    return (
        "/hb-nas-sqlite-bench-" in s
        and (s.startswith("/tmp/") or s.startswith("/private/tmp/"))
    ) or "/app-support/tmp/sqlite-bench-" in s


def _assert_writable_scratch(path: Path) -> None:
    resolved = path.resolve()
    if resolved in DENYLIST_PATHS:
        raise SystemExit(f"refusing write on protected path: {resolved}")
    if not _is_scratch_path(resolved):
        raise SystemExit(f"refusing write outside scratch: {resolved}")


def _percentile_summary(samples_ms: list[float]) -> dict[str, Any]:
    return TimingStats(samples_ms=samples_ms).summary()


def _open_ro(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=30)
    conn.execute("PRAGMA query_only=ON")
    return conn


def _open_rw(path: Path) -> sqlite3.Connection:
    _assert_writable_scratch(path)
    conn = sqlite3.connect(str(path.resolve()), timeout=30)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _table_exists(db_path: Path, table: str) -> bool:
    conn = _open_ro(db_path)
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def _validate_db(path: Path, *, full_integrity: bool = False) -> dict[str, Any]:
    conn = _open_ro(path)
    try:
        quick = conn.execute("PRAGMA quick_check").fetchone()[0]
        schema = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        table_count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0]
        out: dict[str, Any] = {
            "quick_check": quick,
            "schema_version": schema,
            "table_count": table_count,
        }
        if full_integrity:
            out["integrity_check"] = conn.execute("PRAGMA integrity_check").fetchone()[0]
        return out
    finally:
        conn.close()


def _sidecar_report(db_path: Path) -> dict[str, Any]:
    base = Path(db_path)
    sidecars = {}
    for suffix in ("-wal", "-shm", "-journal"):
        p = Path(str(base) + suffix)
        if p.exists():
            sidecars[p.name] = {"path": str(p), "size_bytes": p.stat().st_size}
    return sidecars


def _sidecars_in_scratch_only(sidecars: dict[str, Any]) -> bool:
    if not sidecars:
        return True
    for info in sidecars.values():
        p = str(info["path"])
        if not (
            ("/hb-nas-sqlite-bench-" in p and (p.startswith("/tmp/") or p.startswith("/private/tmp/")))
            or "/app-support/tmp/sqlite-bench-" in p
        ):
            return False
    return True


def cmd_backup(args: argparse.Namespace) -> dict[str, Any]:
    source = Path(args.source).resolve()
    dest = Path(args.dest).resolve()
    if dest.exists() and not args.force:
        raise SystemExit(f"destination exists: {dest} (use --force)")
    _assert_writable_scratch(dest)
    if not source.exists():
        raise SystemExit(f"source missing: {source}")

    before = _file_fingerprint(source)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()

    t0 = time.perf_counter()
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        src.execute("PRAGMA query_only=ON")
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst, pages=1000, sleep=0.05)
            dst.execute("PRAGMA wal_checkpoint(PASSIVE)")
        finally:
            dst.close()
    finally:
        src.close()
    elapsed = round(time.perf_counter() - t0, 3)

    after = _file_fingerprint(source)
    validation = _validate_db(dest, full_integrity=False)

    return {
        "command": "backup",
        "generated_utc": _utc_now(),
        "source_fingerprint_before": before,
        "source_fingerprint_after": after,
        "source_unchanged": before == after,
        "dest_fingerprint": _file_fingerprint(dest),
        "elapsed_seconds": elapsed,
        "validation": validation,
        "sidecars": _sidecar_report(dest),
    }


def _discover_top_tables(conn: sqlite3.Connection, limit: int = 10) -> list[dict[str, Any]]:
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    ]
    counts: list[tuple[str, int]] = []
    for name in tables:
        try:
            c = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            counts.append((name, int(c)))
        except sqlite3.Error:
            continue
    counts.sort(key=lambda x: x[1], reverse=True)
    return [{"table": n, "row_count": c} for n, c in counts[:limit]]


def _time_query(fn: Callable[[], Any], repeats: int) -> TimingStats:
    stats = TimingStats()
    for _ in range(repeats):
        t0 = time.perf_counter()
        try:
            fn()
            stats.add((time.perf_counter() - t0) * 1000)
        except sqlite3.OperationalError as exc:
            stats.add_error(exc)
        except Exception as exc:
            stats.add_error(exc)
    return stats


def _fingerprint_counts(conn: sqlite3.Connection) -> dict[str, int | str]:
    out: dict[str, int | str] = {}
    for table in FINGERPRINT_TABLES:
        try:
            out[table] = int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        except sqlite3.Error as exc:
            out[table] = f"error:{exc.__class__.__name__}"
    return out


def cmd_read(args: argparse.Namespace) -> dict[str, Any]:
    db_path = Path(args.db).resolve()
    repeats = args.repeats
    conn_open = TimingStats()
    for _ in range(10):
        t0 = time.perf_counter()
        c = _open_ro(db_path)
        c.close()
        conn_open.add((time.perf_counter() - t0) * 1000)

    ro = _open_ro(db_path)
    try:
        schema_stats = _time_query(
            lambda: ro.execute("SELECT MAX(version) FROM schema_migrations").fetchone(), repeats
        )
        table_count_stats = _time_query(
            lambda: ro.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'"
            ).fetchone(),
            repeats,
        )
        top_tables = _discover_top_tables(ro, 10)
        count_stats: dict[str, Any] = {}
        for table in READ_COUNT_TABLES:
            stats = _time_query(
                lambda t=table: ro.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone(), repeats
            )
            count_stats[table] = stats.summary()

        migrator_version = None
        migrator_ms = None
        if args.allow_migrator and args.repo_src:
            try:
                sys.path.insert(0, str(Path(args.repo_src).resolve()))
                from hb_assistant.store.migrator import SQLiteMigrator

                t0 = time.perf_counter()
                migrator_version = SQLiteMigrator(str(db_path)).current_version()
                migrator_ms = round((time.perf_counter() - t0) * 1000, 3)
            except Exception as exc:
                migrator_version = f"skipped:{exc.__class__.__name__}"

        quick_check = None
        if args.run_quick_check:
            t0 = time.perf_counter()
            quick_check = {
                "result": ro.execute("PRAGMA quick_check").fetchone()[0],
                "elapsed_ms": round((time.perf_counter() - t0) * 1000, 3),
            }
    finally:
        ro.close()

    return {
        "command": "read",
        "generated_utc": _utc_now(),
        "db_path": str(db_path),
        "connection_open_close": conn_open.summary(),
        "schema_version_query": schema_stats.summary(),
        "table_count_query": table_count_stats.summary(),
        "top_tables_by_row_count": top_tables,
        "count_queries": count_stats,
        "migrator_current_version": migrator_version,
        "migrator_elapsed_ms": migrator_ms,
        "quick_check": quick_check,
    }


def _ensure_bench_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {BENCH_TABLE} (
            id INTEGER PRIMARY KEY,
            batch_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def cmd_write(args: argparse.Namespace) -> dict[str, Any]:
    db_path = Path(args.db).resolve()
    _assert_writable_scratch(db_path)
    before_size = db_path.stat().st_size
    before_sidecars = _sidecar_report(db_path)

    conn = _open_rw(db_path)
    try:
        journal_before = conn.execute("PRAGMA journal_mode").fetchone()[0]
        sync_mode = conn.execute("PRAGMA synchronous").fetchone()[0]
        _ensure_bench_table(conn)

        results: dict[str, Any] = {"journal_mode_before": journal_before, "synchronous": sync_mode}

        auto_stats = TimingStats()
        for i in range(5):
            t0 = time.perf_counter()
            try:
                conn.execute(
                    f"INSERT INTO {BENCH_TABLE} (batch_id, payload, created_at) VALUES (?, ?, ?)",
                    (f"auto-{i}", "x" * 64, _utc_now()),
                )
                conn.commit()
                auto_stats.add((time.perf_counter() - t0) * 1000)
            except sqlite3.OperationalError as exc:
                auto_stats.add_error(exc)
        results["autocommit_single_insert"] = auto_stats.summary()

        for batch_size in (10, 100, 1000):
            stats = TimingStats()
            batch_id = f"batch-{batch_size}-{uuid.uuid4().hex[:8]}"
            t0 = time.perf_counter()
            try:
                conn.execute("BEGIN IMMEDIATE")
                for j in range(batch_size):
                    conn.execute(
                        f"INSERT INTO {BENCH_TABLE} (batch_id, payload, created_at) VALUES (?, ?, ?)",
                        (batch_id, f"p{j}-" + "y" * 32, _utc_now()),
                    )
                conn.commit()
                stats.add((time.perf_counter() - t0) * 1000)
            except sqlite3.OperationalError as exc:
                conn.rollback()
                stats.add_error(exc)
            results[f"batched_insert_{batch_size}"] = stats.summary()

        update_stats = TimingStats()
        t0 = time.perf_counter()
        try:
            conn.execute(
                f"UPDATE {BENCH_TABLE} SET payload = ? WHERE batch_id LIKE 'batch-%'",
                ("updated-" + "z" * 32,),
            )
            conn.commit()
            update_stats.add((time.perf_counter() - t0) * 1000)
        except sqlite3.OperationalError as exc:
            update_stats.add_error(exc)
        results["update_synthetic"] = update_stats.summary()

        delete_stats = TimingStats()
        t0 = time.perf_counter()
        try:
            conn.execute(f"DELETE FROM {BENCH_TABLE} WHERE batch_id LIKE 'auto-%'")
            conn.commit()
            delete_stats.add((time.perf_counter() - t0) * 1000)
        except sqlite3.OperationalError as exc:
            delete_stats.add_error(exc)
        results["delete_synthetic_subset"] = delete_stats.summary()

        journal_after = conn.execute("PRAGMA journal_mode").fetchone()[0]
        bench_rows = conn.execute(f"SELECT COUNT(*) FROM {BENCH_TABLE}").fetchone()[0]
    finally:
        conn.close()

    after_size = db_path.stat().st_size
    after_sidecars = _sidecar_report(db_path)
    return {
        "command": "write",
        "generated_utc": _utc_now(),
        "db_path": str(db_path),
        "journal_mode_after": journal_after,
        "db_size_before_bytes": before_size,
        "db_size_after_bytes": after_size,
        "sidecars_before": before_sidecars,
        "sidecars_after": after_sidecars,
        "sidecars_in_scratch_only": _sidecars_in_scratch_only(after_sidecars),
        "bench_table_row_count": bench_rows,
        "scenarios": results,
    }


def _reader_worker(
    db_path: Path, iterations: int, out: list[float], errors: list[str], stop: threading.Event
) -> None:
    try:
        conn = _open_ro(db_path)
        try:
            for _ in range(iterations):
                if stop.is_set():
                    break
                t0 = time.perf_counter()
                conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
                conn.execute('SELECT COUNT(*) FROM "procore_ep_schedule_activities"').fetchone()
                out.append((time.perf_counter() - t0) * 1000)
        finally:
            conn.close()
    except Exception as exc:
        errors.append(str(exc))


def _writer_worker(
    db_path: Path,
    iterations: int,
    out: list[float],
    busy: list[int],
    retries: list[int],
    errors: list[str],
    stop: threading.Event,
) -> None:
    conn = _open_rw(db_path)
    try:
        _ensure_bench_table(conn)
        for i in range(iterations):
            if stop.is_set():
                break
            t0 = time.perf_counter()
            attempt_used = 0
            for attempt in range(4):
                attempt_used = attempt
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    conn.execute(
                        f"INSERT INTO {BENCH_TABLE} (batch_id, payload, created_at) VALUES (?, ?, ?)",
                        (f"conc-{threading.current_thread().name}-{i}", "c" * 48, _utc_now()),
                    )
                    conn.commit()
                    out.append((time.perf_counter() - t0) * 1000)
                    if attempt > 0:
                        retries[0] += attempt
                    break
                except sqlite3.OperationalError as exc:
                    conn.rollback()
                    msg = str(exc).lower()
                    if "locked" in msg or "busy" in msg:
                        busy[0] += 1
                        time.sleep(0.05 * (attempt + 1))
                        continue
                    errors.append(str(exc))
                    break
            else:
                errors.append("max retries exceeded")
    finally:
        conn.close()


def _run_concurrency_scenario(
    db_path: Path, readers: int, writers: int, iterations: int
) -> dict[str, Any]:
    read_latencies: list[float] = []
    write_latencies: list[float] = []
    read_errors: list[str] = []
    write_errors: list[str] = []
    busy_count = [0]
    retry_count = [0]
    stop = threading.Event()
    threads: list[threading.Thread] = []

    t0 = time.perf_counter()
    for i in range(readers):
        threads.append(
            threading.Thread(
                target=_reader_worker,
                name=f"reader-{i}",
                args=(db_path, iterations, read_latencies, read_errors, stop),
                daemon=True,
            )
        )
    for i in range(writers):
        threads.append(
            threading.Thread(
                target=_writer_worker,
                name=f"writer-{i}",
                args=(db_path, iterations, write_latencies, busy_count, retry_count, write_errors, stop),
                daemon=True,
            )
        )
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=180)
    stop.set()
    duration = round(time.perf_counter() - t0, 3)

    attempted = readers * iterations + writers * iterations
    completed = len(read_latencies) + len(write_latencies)

    return {
        "readers": readers,
        "writers": writers,
        "iterations_per_thread": iterations,
        "duration_seconds": duration,
        "ops_attempted": attempted,
        "ops_completed": completed,
        "read_latency": _percentile_summary(read_latencies),
        "write_latency": _percentile_summary(write_latencies),
        "sqlite_busy_count": busy_count[0],
        "retry_count": retry_count[0],
        "read_errors": len(read_errors),
        "write_errors": len(write_errors),
        "error_samples": (read_errors + write_errors)[:5],
    }


def cmd_concurrency(args: argparse.Namespace) -> dict[str, Any]:
    db_path = Path(args.db).resolve()
    scenarios = [
        (5, 0, 20),
        (10, 0, 20),
        (5, 1, 20),
        (10, 1, 20),
        (1, 1, 30),
    ]
    results = []
    total_busy = 0
    total_retries = 0
    for readers, writers, iters in scenarios:
        r = _run_concurrency_scenario(db_path, readers, writers, iters)
        total_busy += int(r["sqlite_busy_count"])
        total_retries += int(r["retry_count"])
        results.append(r)
    return {
        "command": "concurrency",
        "generated_utc": _utc_now(),
        "db_path": str(db_path),
        "scenarios": results,
        "total_sqlite_busy_count": total_busy,
        "total_retry_count": total_retries,
    }


def cmd_wal(args: argparse.Namespace) -> dict[str, Any]:
    db_path = Path(args.db).resolve()
    _assert_writable_scratch(db_path)
    conn = _open_rw(db_path)
    try:
        mode_before = conn.execute("PRAGMA journal_mode").fetchone()[0]
        t0 = time.perf_counter()
        mode_after = conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        wal_set_ms = round((time.perf_counter() - t0) * 1000, 3)

        _ensure_bench_table(conn)
        t0 = time.perf_counter()
        conn.execute("BEGIN IMMEDIATE")
        for _ in range(100):
            conn.execute(
                f"INSERT INTO {BENCH_TABLE} (batch_id, payload, created_at) VALUES (?, ?, ?)",
                (f"wal-burst-{uuid.uuid4().hex[:8]}", "w" * 40, _utc_now()),
            )
        conn.commit()
        burst_ms = round((time.perf_counter() - t0) * 1000, 3)

        sidecars_mid = _sidecar_report(db_path)

        t0 = time.perf_counter()
        passive = conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
        passive_ms = round((time.perf_counter() - t0) * 1000, 3)

        t0 = time.perf_counter()
        truncate = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        truncate_ms = round((time.perf_counter() - t0) * 1000, 3)

        t0 = time.perf_counter()
        quick = conn.execute("PRAGMA quick_check").fetchone()[0]
        quick_ms = round((time.perf_counter() - t0) * 1000, 3)
    finally:
        conn.close()

    sidecars_after = _sidecar_report(db_path)
    return {
        "command": "wal",
        "generated_utc": _utc_now(),
        "db_path": str(db_path),
        "journal_mode_before": mode_before,
        "journal_mode_after": mode_after,
        "wal_set_ms": wal_set_ms,
        "write_burst_100_rows_ms": burst_ms,
        "checkpoint_passive_ms": passive_ms,
        "checkpoint_passive_result": list(passive),
        "checkpoint_truncate_ms": truncate_ms,
        "checkpoint_truncate_result": list(truncate),
        "quick_check_after": quick,
        "quick_check_ms": quick_ms,
        "sidecars_mid": sidecars_mid,
        "sidecars_after": sidecars_after,
        "sidecars_in_scratch_only": _sidecars_in_scratch_only(sidecars_after),
    }


def cmd_integrity(args: argparse.Namespace) -> dict[str, Any]:
    db_path = Path(args.db).resolve()
    before_fp = json.loads(args.fingerprint_before) if args.fingerprint_before else None
    ro = _open_ro(db_path)
    try:
        after_fp = _fingerprint_counts(ro)
    finally:
        ro.close()

    fp_delta: dict[str, Any] = {}
    if before_fp:
        for k, v in after_fp.items():
            if k in before_fp and before_fp[k] != v:
                fp_delta[k] = {"before": before_fp[k], "after": v}

    validation = _validate_db(db_path, full_integrity=True)
    bench_rows = 0
    if _table_exists(db_path, BENCH_TABLE):
        conn = _open_ro(db_path)
        try:
            bench_rows = conn.execute(f"SELECT COUNT(*) FROM {BENCH_TABLE}").fetchone()[0]
        finally:
            conn.close()

    sidecars = _sidecar_report(db_path)
    return {
        "command": "integrity",
        "generated_utc": _utc_now(),
        "db_path": str(db_path),
        "validation": validation,
        "fingerprint_after": after_fp,
        "fingerprint_delta_unexpected": fp_delta,
        "bench_table_rows": bench_rows,
        "sidecars": sidecars,
        "sidecars_in_scratch_only": _sidecars_in_scratch_only(sidecars),
    }


def cmd_fingerprint(args: argparse.Namespace) -> dict[str, Any]:
    db_path = Path(args.db).resolve()
    ro = _open_ro(db_path)
    try:
        fp = _fingerprint_counts(ro)
    finally:
        ro.close()
    return {"command": "fingerprint", "generated_utc": _utc_now(), "counts": fp}


def cmd_all(args: argparse.Namespace) -> dict[str, Any]:
    out: dict[str, Any] = {"generated_utc": _utc_now(), "steps": {}}
    if args.source and args.dest:
        out["steps"]["backup"] = cmd_backup(
            argparse.Namespace(source=args.source, dest=args.dest, force=True)
        )
    out["steps"]["fingerprint_before"] = cmd_fingerprint(argparse.Namespace(db=args.db))
    out["steps"]["read"] = cmd_read(
        argparse.Namespace(
            db=args.db,
            repeats=args.repeats,
            run_quick_check=False,
            allow_migrator=args.allow_migrator,
            repo_src=args.repo_src,
        )
    )
    out["steps"]["write"] = cmd_write(argparse.Namespace(db=args.db))
    out["steps"]["concurrency"] = cmd_concurrency(argparse.Namespace(db=args.db))
    out["steps"]["wal"] = cmd_wal(argparse.Namespace(db=args.db))
    out["steps"]["integrity"] = cmd_integrity(
        argparse.Namespace(
            db=args.db,
            fingerprint_before=json.dumps(out["steps"]["fingerprint_before"]["counts"]),
        )
    )
    return out


def _add_json_out(p: argparse.ArgumentParser) -> None:
    p.add_argument("--json-out", default="")


def main() -> None:
    parser = argparse.ArgumentParser(description="N4B NAS SQLite benchmark-only tooling")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_backup = sub.add_parser("backup")
    p_backup.add_argument("--source", required=True)
    p_backup.add_argument("--dest", required=True)
    p_backup.add_argument("--force", action="store_true")
    _add_json_out(p_backup)

    p_read = sub.add_parser("read")
    p_read.add_argument("--db", required=True)
    p_read.add_argument("--repeats", type=int, default=5)
    p_read.add_argument("--run-quick-check", action="store_true")
    p_read.add_argument("--allow-migrator", action="store_true")
    p_read.add_argument("--repo-src", default="")
    _add_json_out(p_read)

    for name in ("write", "concurrency", "wal", "fingerprint"):
        p = sub.add_parser(name)
        p.add_argument("--db", required=True)
        _add_json_out(p)

    p_integrity = sub.add_parser("integrity")
    p_integrity.add_argument("--db", required=True)
    p_integrity.add_argument("--fingerprint-before", default="")
    _add_json_out(p_integrity)

    p_all = sub.add_parser("all")
    p_all.add_argument("--db", required=True)
    p_all.add_argument("--source", default="")
    p_all.add_argument("--dest", default="")
    p_all.add_argument("--repeats", type=int, default=5)
    p_all.add_argument("--allow-migrator", action="store_true")
    p_all.add_argument("--repo-src", default="")
    _add_json_out(p_all)

    args = parser.parse_args()

    dispatch = {
        "backup": cmd_backup,
        "read": cmd_read,
        "write": cmd_write,
        "concurrency": cmd_concurrency,
        "wal": cmd_wal,
        "fingerprint": cmd_fingerprint,
        "integrity": cmd_integrity,
        "all": cmd_all,
    }
    result = dispatch[args.cmd](args)
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
