#!/usr/bin/env python3
"""Validate the AEOS Claude Code initial skill package without third-party dependencies."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

EXPECTED = [
    "aeos-goal-controller",
    "aeos-repository-truth",
    "aeos-checkpoint-manager",
    "aeos-implementation-planner",
    "aeos-work-package-executor",
    "aeos-evidence-packager",
    "aeos-independent-auditor",
    "aeos-finding-reconciler",
]

REQUIRED_SHARED = [
    "AEOS_SKILL_OPERATING_CONTRACT.md",
    "templates/goal-charter.template.md",
    "templates/governance-manifest.template.yaml",
    "templates/state.template.yaml",
    "templates/checkpoint-request.template.yaml",
    "templates/authorization.template.yaml",
    "templates/external-review.template.yaml",
    "templates/work-item-ledger.template.yaml",
    "templates/finding-ledger.template.yaml",
    "templates/evidence-index.template.json",
    "schemas/checkpoint-request.schema.json",
    "schemas/evidence-index.schema.json",
    "schemas/finding-ledger.schema.json",
    "schemas/state.schema.json",
]

DISALLOWED = [
    r"continue\s+until\s+the\s+entire\s+goal\s+is\s+complete",
    r"automatically\s+approve",
    r"self[- ]approve",
    r"bypass\s+(?:the\s+)?operator",
]

FRONT_MATTER = re.compile(
    r"\A---\s*\n(?P<header>.*?)\n---\s*\n",
    re.DOTALL,
)

def parse_header(text: str) -> dict[str, str]:
    match = FRONT_MATTER.search(text)
    if not match:
        raise ValueError("missing YAML front matter")
    result: dict[str, str] = {}
    for raw in match.group("header").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if ":" not in raw:
            raise ValueError(f"invalid front matter line: {raw!r}")
        key, value = raw.split(":", 1)
        result[key.strip()] = value.strip()
    return result

def main() -> int:
    script = Path(__file__).resolve()
    skills_root = script.parents[2]
    shared = skills_root / "_aeos-shared"
    errors: list[str] = []
    names: list[str] = []

    for skill_name in EXPECTED:
        path = skills_root / skill_name / "SKILL.md"
        if not path.is_file():
            errors.append(f"missing {path}")
            continue
        text = path.read_text(encoding="utf-8")
        try:
            header = parse_header(text)
        except ValueError as exc:
            errors.append(f"{path}: {exc}")
            continue
        if header.get("name") != skill_name:
            errors.append(
                f"{path}: name={header.get('name')!r}, expected {skill_name!r}"
            )
        description = header.get("description", "")
        if len(description) < 30:
            errors.append(f"{path}: description is too short")
        names.append(header.get("name", ""))
        for pattern in DISALLOWED:
            if re.search(pattern, text, flags=re.IGNORECASE):
                errors.append(f"{path}: disallowed broad-autonomy wording: {pattern}")

    if len(names) != len(set(names)):
        errors.append("duplicate skill names")

    for rel in REQUIRED_SHARED:
        path = shared / rel
        if not path.is_file():
            errors.append(f"missing shared resource: {path}")

    for path in (shared / "schemas").glob("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{path}: invalid JSON: {exc}")

    # Validate local Markdown links only within the canonical skill corpus.
    # Do not scan the enclosing repository, virtual environments, worktrees,
    # or unrelated documentation when this script is reached through a symlink.
    package_root = skills_root
    link_re = re.compile(r"\[[^\]]+\]\((?!https?://|#)([^)]+)\)")
    for md in package_root.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        for target in link_re.findall(text):
            target = target.split("#", 1)[0]
            if not target:
                continue
            resolved = (md.parent / target).resolve()
            if not resolved.exists():
                errors.append(f"{md}: broken local link {target!r}")

    if errors:
        print("AEOS skill package validation: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("AEOS skill package validation: PASS")
    print(f"- skills root: {skills_root}")
    print(f"- skills: {len(EXPECTED)}")
    print(f"- shared resources: {len(REQUIRED_SHARED)} required files present")
    return 0

if __name__ == "__main__":
    sys.exit(main())
