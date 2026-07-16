#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

EXPECTED_SKILLS = [
    "aeos-goal-controller",
    "aeos-repository-truth",
    "aeos-checkpoint-manager",
    "aeos-implementation-planner",
    "aeos-work-package-executor",
    "aeos-evidence-packager",
    "aeos-independent-auditor",
    "aeos-finding-reconciler",
]

def main() -> int:
    root = Path(__file__).resolve().parents[2]
    errors = []

    required = [
        root / "README.md",
        root / "project-sources" / "00_AEOS_MASTER_INDEX.md",
        root / "agent-skills" / "_aeos-shared" / "AEOS_SKILL_OPERATING_CONTRACT.md",
        root / "agent-harnesses" / "claude" / "README.md",
        root / "agent-harnesses" / "codex" / "README.md",
        root / "agent-harnesses" / "grok" / "grok-system-prompt.md",
        root / "aeos" / "bin" / "install_harness_links.py",
    ]
    for path in required:
        if not path.exists():
            errors.append(f"missing {path.relative_to(root)}")

    for skill in EXPECTED_SKILLS:
        path = root / "agent-skills" / skill / "SKILL.md"
        if not path.is_file():
            errors.append(f"missing skill {skill}")
        meta = root / "agent-skills" / skill / "agents" / "openai.yaml"
        if not meta.is_file():
            errors.append(f"missing Codex metadata for {skill}")

    forbidden = [root / ".DS_Store", root.parent / "__MACOSX"]
    for path in forbidden:
        if path.exists():
            errors.append(f"forbidden macOS metadata: {path}")

    if errors:
        print("AI layout validation: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("AI layout validation: PASS")
    print(f"- canonical skills: {len(EXPECTED_SKILLS)}")
    print("- canonical AEOS source path: .ai/project-sources/")
    print("- harness adapters: Claude, Codex, Grok")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
