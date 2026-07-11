#!/usr/bin/env python3
"""Large-scale metadata-first source-index scan benchmark (deployment-readiness gate 1).

Builds a synthetic source tree of N files, then runs bounded metadata-first scan passes through the
V122 generation authority to completion, measuring:

* number of bounded passes (proves the walk resumes one durable generation across many passes),
* peak process RSS (proves memory is bounded by the per-pass cap, NOT the tree size),
* throughput (files/sec) and wall time,
* that ZERO content rows are produced (metadata-first: never reads/parses/chunks a file),
* that every file is discoverable by path after the scan (active row count == tree size).

Scratch DB + synthetic temp tree ONLY — never touches the production DB, config, or any NAS mount.

Usage:
    python scripts/source_index_scan_benchmark.py --files 400000 --max-files-per-pass 25000
    python scripts/source_index_scan_benchmark.py --files 100000 --json-out bench.json
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import shutil
import sys
import tempfile
import time
from pathlib import Path


def _peak_rss_mb() -> float:
    """Peak resident set size of this process, in MiB. ``ru_maxrss`` is bytes on macOS, KiB on Linux."""
    ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
    return round(ru / divisor, 1)


def _build_tree(root: Path, n_files: int, files_per_dir: int) -> float:
    """Create ``n_files`` tiny files under ``root`` spread across subdirectories. Returns wall seconds."""
    t0 = time.time()
    blob = b"x" * 64  # small non-empty payload; metadata-first never reads it
    made = 0
    d = -1
    cur: Path | None = None
    while made < n_files:
        if made % files_per_dir == 0:
            d += 1
            cur = root / f"d{d:05d}"
            cur.mkdir(parents=True, exist_ok=True)
        assert cur is not None
        fd = os.open(cur / f"f{made:07d}.txt", os.O_WRONLY | os.O_CREAT, 0o644)
        os.write(fd, blob)
        os.close(fd)
        made += 1
    return round(time.time() - t0, 2)


def run_benchmark(n_files: int, files_per_dir: int, max_files_per_pass: int, workdir: str | None) -> dict:
    # Local imports so `--help` works without the package import cost / path setup.
    from hb_assistant.obsidian_mcp import source_indexer as si
    from hb_assistant.obsidian_mcp.config import ExternalSourceRoot, ObsidianMcpConfig
    from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
    from hb_assistant.store.migrator import SQLiteMigrator

    base = Path(tempfile.mkdtemp(prefix="si-bench-", dir=workdir))
    try:
        db = str(base / "bench.db")
        SQLiteMigrator(db_path=db).apply()
        root = base / "tree"
        root.mkdir()
        build_s = _build_tree(root, n_files, files_per_dir)

        repo = SourceIndexRepository(db)
        r = ExternalSourceRoot(source_root_key="bench", path=str(root))
        cfg = ObsidianMcpConfig(
            vault_root=str(base),
            external_sources=[r],
            external_source_index_enabled=True,
        )

        rss_start = _peak_rss_mb()
        t0 = time.time()
        passes = 0
        status = None
        for _ in range(10_000):  # generous ceiling; bounded passes converge well under this
            rep = si.scan_source_root(r, repo, cfg, max_files_per_pass=max_files_per_pass)
            passes += 1
            status = rep.generation_status
            if status in ("completed", "failed"):
                break
        scan_s = time.time() - t0

        active = len(repo.active_rel_paths("bench"))
        content_rows = repo.count_content_searchable("bench") if hasattr(repo, "count_content_searchable") else None
        # Fallback content check via a direct query if the helper is absent.
        if content_rows is None:
            import sqlite3

            c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                content_rows = c.execute(
                    "SELECT COUNT(*) FROM source_intelligence_metadata WHERE content_indexed_at IS NOT NULL"
                ).fetchone()[0]
            finally:
                c.close()
        db_mb = round(os.path.getsize(db) / (1024 * 1024), 1)

        return {
            "files_requested": n_files,
            "files_indexed": active,
            "all_files_discoverable": active == n_files,
            "content_rows": content_rows,
            "metadata_only_zero_content": content_rows == 0,
            "bounded_passes": passes,
            "resumed_across_multiple_passes": passes >= 2,
            "final_status": status,
            "max_files_per_pass": max_files_per_pass,
            "tree_build_seconds": build_s,
            "scan_seconds": round(scan_s, 2),
            "files_per_second": round(n_files / scan_s, 1) if scan_s > 0 else None,
            "peak_rss_mb": _peak_rss_mb(),
            "rss_at_start_mb": rss_start,
            "db_size_mb": db_mb,
        }
    finally:
        shutil.rmtree(base, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--files", type=int, default=400_000, help="Total synthetic files (default 400000).")
    ap.add_argument("--files-per-dir", type=int, default=1000, help="Files per subdirectory (default 1000).")
    ap.add_argument("--max-files-per-pass", type=int, default=25_000, help="Per-pass observed-file cap.")
    ap.add_argument("--workdir", default=None, help="Parent dir for the temp tree (default system temp).")
    ap.add_argument("--json-out", default=None, help="Write the result JSON to this path.")
    args = ap.parse_args()

    result = run_benchmark(args.files, args.files_per_dir, args.max_files_per_pass, args.workdir)
    print(json.dumps(result, indent=2))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    # Non-zero exit if the benchmark's core invariants did not hold (useful as a gate).
    ok = (
        result["all_files_discoverable"]
        and result["metadata_only_zero_content"]
        and result["resumed_across_multiple_passes"]
        and result["final_status"] == "completed"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
