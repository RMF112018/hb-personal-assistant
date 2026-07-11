"""Keeps the deployment-readiness benchmark harness (scripts/source_index_scan_benchmark.py) alive.

Runs it at a SMALL scale so CI regression-checks the harness + the core scan invariants it asserts
(bounded multi-pass resume, metadata-only zero-content, full path discoverability, bounded memory)
without paying for a 400k run. The full-scale 400k evidence is captured out-of-band.

Scratch DB + synthetic temp tree only.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "source_index_scan_benchmark.py"


def _load():
    spec = importlib.util.spec_from_file_location("si_scan_benchmark", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_benchmark_harness_invariants_small_scale(tmp_path):
    bench = _load()
    r = bench.run_benchmark(
        n_files=3000, files_per_dir=500, max_files_per_pass=800, workdir=str(tmp_path)
    )
    assert r["files_indexed"] == 3000
    assert r["all_files_discoverable"] is True
    assert r["metadata_only_zero_content"] is True  # never reads/parses content
    assert r["content_rows"] == 0
    assert r["resumed_across_multiple_passes"] is True  # >=2 bounded passes, one generation
    assert r["bounded_passes"] >= 2
    assert r["final_status"] == "completed"
    assert r["peak_rss_mb"] > 0
