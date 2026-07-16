#!/usr/bin/env python3
from __future__ import annotations
import argparse
import os
from pathlib import Path

SKILLS = [
    "_aeos-shared",
    "aeos-goal-controller",
    "aeos-repository-truth",
    "aeos-checkpoint-manager",
    "aeos-implementation-planner",
    "aeos-work-package-executor",
    "aeos-evidence-packager",
    "aeos-independent-auditor",
    "aeos-finding-reconciler",
]

def repo_root() -> Path:
    current = Path.cwd().resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists() or (candidate / "AGENTS.md").exists():
            return candidate
    raise SystemExit("Run inside the repository.")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--harness", choices=["claude", "codex", "all"], required=True)
    parser.add_argument("--replace", action="store_true",
                        help="Replace an existing symlink only; never delete a real directory.")
    args = parser.parse_args()

    root = repo_root()
    canonical = root / ".ai" / "agent-skills"
    if not canonical.is_dir():
        raise SystemExit(f"Missing canonical skill root: {canonical}")

    targets = []
    if args.harness in ("claude", "all"):
        targets.append(root / ".claude" / "skills")
    if args.harness in ("codex", "all"):
        targets.append(root / ".agents" / "skills")

    for target_root in targets:
        target_root.mkdir(parents=True, exist_ok=True)
        for name in SKILLS:
            source = canonical / name
            target = target_root / name
            if not source.exists():
                raise SystemExit(f"Missing canonical skill: {source}")
            if target.exists() or target.is_symlink():
                if target.is_symlink() and args.replace:
                    target.unlink()
                else:
                    print(f"SKIP existing non-replaced path: {target}")
                    continue
            relative = os.path.relpath(source, target.parent)
            target.symlink_to(relative, target_is_directory=True)
            print(f"LINK {target} -> {relative}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
