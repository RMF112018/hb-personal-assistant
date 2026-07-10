#!/usr/bin/env python3
"""Compare failing pytest node IDs between feature and baseline (not modules only)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = os.environ.get("PYTHON", sys.executable)
MODULES = [
    "tests/test_n8c23_mcp_surface_safety.py",
    "tests/test_prompt_preflight_routing_consistency.py",
    "tests/test_canonical_tool_surface_parity.py",
    "tests/test_nas_mcp_tool_annotations.py",
    "tests/test_n8c_final_validation.py",
]


def collect_failures(cwd: Path, modules: list[str]) -> dict:
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.time()
    failed: list[str] = []
    passed = 0
    collected = 0
    for mod in modules:
        if not (cwd / mod).exists():
            continue
        p = subprocess.run(
            [PY, "-m", "pytest", "-q", "--tb=no", mod],
            cwd=cwd,
            env={**os.environ, "PYTHONPATH": "src"},
            capture_output=True,
            text=True,
            timeout=180,
        )
        out = p.stdout + p.stderr
        # Count from summary line when possible
        for line in out.splitlines():
            if line.startswith("FAILED "):
                failed.append(line.split()[1])
        # crude pass count from dots is hard; use --collect-only count
        c = subprocess.run(
            [PY, "-m", "pytest", "--collect-only", "-q", mod],
            cwd=cwd,
            env={**os.environ, "PYTHONPATH": "src"},
            capture_output=True,
            text=True,
            timeout=60,
        )
        for line in c.stdout.splitlines():
            if " test" in line and "selected" in line:
                pass
            if line.strip().endswith("tests") or "selected" in line:
                try:
                    # e.g. "10 tests collected"
                    parts = line.strip().split()
                    if parts and parts[0].isdigit():
                        collected += int(parts[0])
                except Exception:
                    pass
        if p.returncode == 0:
            # estimate passed
            pass
    ended = datetime.now(timezone.utc).isoformat()
    return {
        "failed_nodes": sorted(set(failed)),
        "started": started,
        "ended": ended,
        "duration_s": round(time.time() - t0, 1),
        "modules": modules,
        "exit_hint": "see per-module",
    }


def main() -> int:
    feature = Path(os.environ.get(
        "FEATURE_ROOT",
        str(ROOT),
    ))
    baseline = Path(os.environ.get(
        "BASELINE_ROOT",
        str(Path.home() / "hb-personal-assistant-worktrees/baseline-05765b65"),
    ))
    feat_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=feature, text=True).strip()
    base_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=baseline, text=True).strip()

    print("feature", feature, feat_sha)
    print("baseline", baseline, base_sha)
    f = collect_failures(feature, MODULES)
    b = collect_failures(baseline, MODULES)
    f_set, b_set = set(f["failed_nodes"]), set(b["failed_nodes"])
    report = {
        "feature_sha": feat_sha,
        "baseline_sha": base_sha,
        "command": "pytest -q --tb=no <modules>",
        "python": sys.version.split()[0],
        "feature": f,
        "baseline": b,
        "common_failing_both": sorted(f_set & b_set),
        "common_failing_only_feature": sorted(f_set - b_set),
        "common_fixed_on_feature": sorted(b_set - f_set),
        "feature_failed_count": len(f_set),
        "baseline_failed_count": len(b_set),
    }
    out = ROOT / "docs/evidence/prompt-preflight-routing-consistency"
    out.mkdir(parents=True, exist_ok=True)
    (out / "suite-node-comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    md = [
        "# Suite node comparison",
        "",
        f"- Feature SHA: `{feat_sha}`",
        f"- Baseline SHA: `{base_sha}`",
        f"- Feature failed nodes: {len(f_set)}",
        f"- Baseline failed nodes: {len(b_set)}",
        "",
        "## NEW (fail only on feature)",
        "",
    ]
    for n in report["common_failing_only_feature"]:
        md.append(f"- `{n}`")
    if not report["common_failing_only_feature"]:
        md.append("- *(none)*")
    md += ["", "## PRE-EXISTING (both)", ""]
    for n in report["common_failing_both"]:
        md.append(f"- `{n}`")
    md += ["", "## FIXED on feature", ""]
    for n in report["common_fixed_on_feature"]:
        md.append(f"- `{n}`")
    if not report["common_fixed_on_feature"]:
        md.append("- *(none)*")
    (out / "suite-node-comparison.md").write_text("\n".join(md) + "\n")
    print(json.dumps({
        "new": report["common_failing_only_feature"],
        "pre": report["common_failing_both"],
        "fixed": report["common_fixed_on_feature"],
    }, indent=2))
    # Exit nonzero only if full_loop is a new failure
    bad = [n for n in report["common_failing_only_feature"] if "full_loop" in n]
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
