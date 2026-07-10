#!/usr/bin/env python3
"""Run offline-safe 77-module batch and collect failing pytest node IDs.

Evidence hygiene helper — not a behavioral change.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PATTERNS = [
    "test_prompt*.py",
    "test_tool*.py",
    "test_n8c*.py",
    "test_nas*.py",
    "test_source*.py",
    "test_canonical*.py",
]


def modules(root: Path) -> list[Path]:
    files: list[Path] = []
    for pat in PATTERNS:
        files.extend(sorted((root / "tests").glob(pat)))
    return sorted(set(files), key=lambda p: p.name)


def run_batch(root: Path, label: str, out_dir: Path) -> dict:
    py = os.environ.get("PYTHON", sys.executable)
    files = modules(root)
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    title = subprocess.check_output(
        ["git", "log", "-1", "--format=%s"], cwd=root, text=True
    ).strip()
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.time()
    lines: list[str] = [
        f"=== {label} modules={len(files)} ===",
        f"sha={sha}",
        f"title={title}",
        f"started_utc={started}",
        f"python={sys.version.split()[0]}",
        f"command=pytest -q --tb=line <module> (timeout 120s per module)",
        f"patterns={PATTERNS}",
        "",
    ]
    failed_nodes: list[str] = []
    pass_m = fail_m = timeout_m = 0
    env = {**os.environ, "PYTHONPATH": "src"}
    for f in files:
        rel = str(f.relative_to(root))
        try:
            p = subprocess.run(
                [py, "-m", "pytest", "-q", "--tb=line", rel],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            out = p.stdout + p.stderr
            nodes = []
            for line in out.splitlines():
                if line.startswith("FAILED "):
                    node = line.split()[1]
                    nodes.append(node)
                    failed_nodes.append(node)
            if p.returncode == 0:
                pass_m += 1
                lines.append(f"PASS {rel}")
            else:
                fail_m += 1
                lines.append(f"FAIL {rel} nodes={nodes}")
        except subprocess.TimeoutExpired:
            timeout_m += 1
            lines.append(f"TIMEOUT {rel}")
            failed_nodes.append(f"{rel}::TIMEOUT")
    dur = time.time() - t0
    ended = datetime.now(timezone.utc).isoformat()
    summary = (
        f"SUMMARY {label} pass={pass_m} fail={fail_m} timeout={timeout_m} "
        f"total={len(files)} duration_s={dur:.1f} failed_nodes={len(set(failed_nodes))}"
    )
    lines.append(summary)
    lines.append(f"ended_utc={ended}")
    if failed_nodes:
        lines.append("FAILED_NODES:")
        for n in sorted(set(failed_nodes)):
            lines.append(n)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"suite-{label}-batch-{sha[:12]}"
    (out_dir / f"{stem}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload = {
        "label": label,
        "sha": sha,
        "title": title,
        "started_utc": started,
        "ended_utc": ended,
        "duration_s": round(dur, 1),
        "python": sys.version.split()[0],
        "pass_modules": pass_m,
        "fail_modules": fail_m,
        "timeout_modules": timeout_m,
        "total_modules": len(files),
        "failed_nodes": sorted(set(failed_nodes)),
        "patterns": PATTERNS,
        "per_module_timeout_s": 120,
    }
    (out_dir / f"{stem}.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(summary)
    print("nodes", sorted(set(failed_nodes)))
    return payload


def compare(feature: dict, baseline: dict, out_dir: Path) -> None:
    f, b = set(feature["failed_nodes"]), set(baseline["failed_nodes"])
    report = {
        "feature_sha": feature["sha"],
        "baseline_sha": baseline["sha"],
        "feature_title": feature["title"],
        "baseline_title": baseline.get("title"),
        "common_failing_both": sorted(f & b),
        "common_failing_only_feature": sorted(f - b),
        "common_fixed_on_feature": sorted(b - f),
        "feature_failed_nodes": sorted(f),
        "baseline_failed_nodes": sorted(b),
        "feature_module_summary": {
            "pass": feature["pass_modules"],
            "fail": feature["fail_modules"],
            "timeout": feature["timeout_modules"],
            "total": feature["total_modules"],
            "duration_s": feature["duration_s"],
        },
        "baseline_module_summary": {
            "pass": baseline["pass_modules"],
            "fail": baseline["fail_modules"],
            "timeout": baseline["timeout_modules"],
            "total": baseline["total_modules"],
            "duration_s": baseline["duration_s"],
        },
        "note": (
            "Node-level classification for the full 77-module offline-safe batch. "
            "Supersedes suite-feature-head-ee06db39.txt and suite-comparison-head.md."
        ),
    }
    (out_dir / "suite-comparison-current.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    md = [
        "# Suite comparison (current — authoritative)",
        "",
        f"**Feature SHA:** `{feature['sha']}`  ",
        f"**Feature title:** {feature['title']}  ",
        f"**Baseline SHA:** `{baseline['sha']}`  ",
        "",
        "Scope: offline-safe module batch "
        "`test_prompt*`, `test_tool*`, `test_n8c*`, `test_nas*`, `test_source*`, `test_canonical*` "
        "(120s per-module timeout).",
        "",
        "## Module summaries",
        "",
        f"| | Feature | Baseline |",
        f"| --- | ---: | ---: |",
        f"| pass modules | {feature['pass_modules']} | {baseline['pass_modules']} |",
        f"| fail modules | {feature['fail_modules']} | {baseline['fail_modules']} |",
        f"| timeout modules | {feature['timeout_modules']} | {baseline['timeout_modules']} |",
        f"| total modules | {feature['total_modules']} | {baseline['total_modules']} |",
        f"| duration_s | {feature['duration_s']} | {baseline['duration_s']} |",
        "",
        "## Node-level classification",
        "",
        "### NEW (fail only on feature)",
        "",
    ]
    if report["common_failing_only_feature"]:
        for n in report["common_failing_only_feature"]:
            md.append(f"- `{n}`")
    else:
        md.append("- *(none)*")
    md += ["", "### PRE-EXISTING (fail on both)", ""]
    for n in report["common_failing_both"]:
        md.append(f"- `{n}`")
    if not report["common_failing_both"]:
        md.append("- *(none)*")
    md += ["", "### FIXED on feature (baseline fail, feature pass)", ""]
    for n in report["common_fixed_on_feature"]:
        md.append(f"- `{n}`")
    if not report["common_fixed_on_feature"]:
        md.append("- *(none)*")
    md += [
        "",
        "## Superseded artifacts",
        "",
        "The following are **historical only** and must not be used as current closeout truth:",
        "",
        "- `suite-feature-head-ee06db39.txt` (pre-vault-projection fix; full_loop failed)",
        "- `suite-comparison-head.md` (module-level summary at ee06db39)",
        "- `suite-feature-batch.txt` / `suite-baseline-batch.txt` (earlier intermediate runs)",
        "",
        "Targeted node comparison in `suite-node-comparison.md` covers a **narrow module set** "
        "for quick regression triage; this file is the authoritative 77-module node classification.",
        "",
        "## Exact-ID / has_exact_id coverage (not in 20-row route matrix)",
        "",
        "These cases are asserted in unit tests, not the offline route matrix:",
        "",
        "- `tests/test_prompt_preflight_routing_consistency.py::test_decision_exact_id_populates_args`",
        "  - Validated ID in prompt → getter arguments populated when getter is recommended",
        "  - `has_exact_id=True` without extractable ID → no invented arguments",
        "- `tests/test_prompt_preflight_routing_consistency.py::test_decision_discovery_first_without_id`",
        "  - Broad topic prompt → list first; getter non-executable without ID",
        "",
    ]
    (out_dir / "suite-comparison-current.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({
        "new": report["common_failing_only_feature"],
        "pre": report["common_failing_both"],
        "fixed": report["common_fixed_on_feature"],
    }, indent=2))


def main() -> int:
    feature = Path(os.environ.get(
        "FEATURE_ROOT",
        str(Path(__file__).resolve().parents[1]),
    ))
    baseline = Path(os.environ.get(
        "BASELINE_ROOT",
        str(Path.home() / "hb-personal-assistant-worktrees/baseline-05765b65"),
    ))
    out = feature / "docs/evidence/prompt-preflight-routing-consistency"
    feat = run_batch(feature, "feature", out)
    base = run_batch(baseline, "baseline", out)
    compare(feat, base, out)
    # Fail only if full_loop appears as feature-only
    if any("full_loop" in n for n in feat["failed_nodes"] if n not in base["failed_nodes"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
