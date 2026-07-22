#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = ROOT.parent
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
PROHIBITED_SCHEMA_NAMES = {
    "aeos_artifact_metadata.schema.json",
    "aeos_finding.schema.json",
    "aeos_go_no_go.schema.json",
}
PAIRED_RESOURCES = [
    ("templates/goal-loop/state.template.yaml", "agent-skills/_aeos-shared/templates/state.template.yaml"),
    ("templates/goal-loop/checkpoint-request.template.yaml", "agent-skills/_aeos-shared/templates/checkpoint-request.template.yaml"),
    ("templates/goal-loop/evidence-index.template.json", "agent-skills/_aeos-shared/templates/evidence-index.template.json"),
    ("templates/goal-loop/authorization.template.yaml", "agent-skills/_aeos-shared/templates/authorization.template.yaml"),
    ("templates/goal-loop/external-review.template.yaml", "agent-skills/_aeos-shared/templates/external-review.template.yaml"),
    ("templates/goal-loop/finding-ledger.template.yaml", "agent-skills/_aeos-shared/templates/finding-ledger.template.yaml"),
    ("templates/goal-loop/governance-manifest.template.yaml", "agent-skills/_aeos-shared/templates/governance-manifest.template.yaml"),
    ("templates/goal-loop/work-item-ledger.template.yaml", "agent-skills/_aeos-shared/templates/work-item-ledger.template.yaml"),
    ("schemas/goal-loop/state.schema.json", "agent-skills/_aeos-shared/schemas/state.schema.json"),
    ("schemas/goal-loop/checkpoint-request.schema.json", "agent-skills/_aeos-shared/schemas/checkpoint-request.schema.json"),
    ("schemas/goal-loop/evidence-index.schema.json", "agent-skills/_aeos-shared/schemas/evidence-index.schema.json"),
    ("schemas/goal-loop/authorization.schema.json", "agent-skills/_aeos-shared/schemas/authorization.schema.json"),
    ("schemas/goal-loop/external-review.schema.json", "agent-skills/_aeos-shared/schemas/external-review.schema.json"),
    ("schemas/goal-loop/finding-ledger.schema.json", "agent-skills/_aeos-shared/schemas/finding-ledger.schema.json"),
    ("schemas/goal-loop/governance-manifest.schema.json", "agent-skills/_aeos-shared/schemas/governance-manifest.schema.json"),
    ("schemas/goal-loop/work-item-ledger.schema.json", "agent-skills/_aeos-shared/schemas/work-item-ledger.schema.json"),
    ("schemas/goal-loop/legacy-v1/state.schema.json", "agent-skills/_aeos-shared/schemas/legacy-v1/state.schema.json"),
    ("schemas/goal-loop/legacy-v1/checkpoint-request.schema.json", "agent-skills/_aeos-shared/schemas/legacy-v1/checkpoint-request.schema.json"),
    ("schemas/goal-loop/legacy-v1/evidence-index.schema.json", "agent-skills/_aeos-shared/schemas/legacy-v1/evidence-index.schema.json"),
    ("schemas/goal-loop/legacy-v1/README.md", "agent-skills/_aeos-shared/schemas/legacy-v1/README.md"),
]
REQUIRED_POINTERS = {
    REPO_ROOT / "AI_OPERATING_MANUAL.md": [
        "docs/decisions/ADR-019-github-first-engineering-control-plane.md",
        "docs/governance/branch-worktree-lifecycle-policy.md",
        ".ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md",
        "MERGED_PENDING_CLEANUP",
    ],
    ROOT / "README.md": [
        "docs/decisions/ADR-019-github-first-engineering-control-plane.md",
        "docs/governance/branch-worktree-lifecycle-policy.md",
        "root/shared",
        "MERGED_PENDING_CLEANUP",
    ],
    ROOT / "project-sources" / "00_AEOS_MASTER_INDEX.md": [
        "11_REPOSITORY_TEST_SELECTION_STANDARD.md",
        "Post-Merge Validation",
        "Branch/Worktree Closeout",
        "MERGED_PENDING_CLEANUP",
    ],
    ROOT / "agent-skills" / "_aeos-shared" / "AEOS_SKILL_OPERATING_CONTRACT.md": [
        "Truth precedence",
        "Action authority",
        "MERGED_PENDING_CLEANUP",
        "preservation",
    ],
}


def is_macos_metadata(path: Path) -> bool:
    return (
        path.name == ".DS_Store"
        or path.name.startswith("._")
        or "__MACOSX" in path.parts
    )


def parse_checksums(path: Path) -> tuple[dict[str, str], list[str]]:
    values: dict[str, str] = {}
    errors: list[str] = []
    if not path.is_file():
        return values, ["missing CHECKSUMS.txt"]
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            digest, rel = line.split("  ", 1)
        except ValueError:
            errors.append(f"CHECKSUMS.txt:{lineno}: malformed line")
            continue
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            errors.append(f"CHECKSUMS.txt:{lineno}: invalid SHA-256")
            continue
        if rel in values:
            errors.append(f"CHECKSUMS.txt:{lineno}: duplicate path {rel}")
            continue
        values[rel] = digest
    return values, errors


def expected_checksums() -> dict[str, str]:
    result: dict[str, str] = {}
    output = ROOT / "CHECKSUMS.txt"
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path == output or is_macos_metadata(path) or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        result[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def main() -> int:
    errors: list[str] = []

    required = [
        ROOT / "README.md",
        ROOT / "AGENT-SKILLS-MANIFEST.json",
        ROOT / "project-sources" / "00_AEOS_MASTER_INDEX.md",
        ROOT / "project-sources" / "11_REPOSITORY_TEST_SELECTION_STANDARD.md",
        ROOT / "agent-skills" / "_aeos-shared" / "AEOS_SKILL_OPERATING_CONTRACT.md",
        ROOT / "agent-harnesses" / "claude" / "README.md",
        ROOT / "agent-harnesses" / "codex" / "README.md",
        ROOT / "agent-harnesses" / "grok" / "grok-system-prompt.md",
        ROOT / "aeos" / "bin" / "install_harness_links.py",
        REPO_ROOT / "AI_OPERATING_MANUAL.md",
        REPO_ROOT / "docs" / "decisions" / "ADR-019-github-first-engineering-control-plane.md",
        REPO_ROOT / "docs" / "governance" / "branch-worktree-lifecycle-policy.md",
        ROOT / "aeos" / "bin" / "validate_goal_loop_contracts.py",
        REPO_ROOT / ".github" / "workflows" / "aeos-governance-validation.yml",
    ]
    for path in required:
        if not path.exists():
            errors.append(f"missing {path.relative_to(REPO_ROOT)}")

    for path in ROOT.rglob("*"):
        if is_macos_metadata(path):
            errors.append(f"forbidden macOS metadata: {path.relative_to(ROOT)}")
        if path.is_file() and path.name in PROHIBITED_SCHEMA_NAMES:
            errors.append(f"prohibited legacy schema: {path.relative_to(ROOT)}")

    for skill in EXPECTED_SKILLS:
        skill_path = ROOT / "agent-skills" / skill / "SKILL.md"
        metadata_path = ROOT / "agent-skills" / skill / "agents" / "openai.yaml"
        if not skill_path.is_file():
            errors.append(f"missing skill {skill}")
        if not metadata_path.is_file():
            errors.append(f"missing Codex metadata for {skill}")

    for left_rel, right_rel in PAIRED_RESOURCES:
        left = ROOT / left_rel
        right = ROOT / right_rel
        if not left.is_file() or not right.is_file():
            errors.append(f"missing paired resource: {left_rel} <-> {right_rel}")
        elif left.read_bytes() != right.read_bytes():
            errors.append(f"divergent paired resource: {left_rel} <-> {right_rel}")

    for path, needles in REQUIRED_POINTERS.items():
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                errors.append(f"{path.relative_to(REPO_ROOT)} missing required pointer/text: {needle}")

    manifest_path = ROOT / "AGENT-SKILLS-MANIFEST.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"invalid AGENT-SKILLS-MANIFEST.json: {exc}")
        else:
            if manifest.get("schema_version") != 2:
                errors.append("AGENT-SKILLS-MANIFEST.json schema_version must be 2")
            if manifest.get("skills_version") != "1.2.0":
                errors.append("AGENT-SKILLS-MANIFEST.json skills_version must be 1.2.0")
            if manifest.get("skills") != EXPECTED_SKILLS:
                errors.append("AGENT-SKILLS-MANIFEST.json skill order/content mismatch")
            required_rules = [
                "exact_head_binding_required",
                "merge_does_not_close_goal",
                "post_merge_closeout_receipt_required",
                "cleanup_actions_require_separate_authorization",
                "root_shared_goal_loop_resources_must_match",
                "representation_scoped_hashes_required",
                "canonical_goal_loop_schema_version_2_only",
                "legacy_v1_requires_registry",
                "semantic_schema_and_yaml_validation_required",
            ]
            rules = manifest.get("rules", {})
            for rule in required_rules:
                if rules.get(rule) is not True:
                    errors.append(f"AGENT-SKILLS-MANIFEST.json rule must be true: {rule}")

    for path in ROOT.rglob("*.json"):
        if path.name == "AGENT-SKILLS-MANIFEST.json":
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"invalid JSON {path.relative_to(ROOT)}: {exc}")

    semantic = subprocess.run([sys.executable, str(ROOT / "aeos" / "bin" / "validate_goal_loop_contracts.py"), "--quiet"], capture_output=True, text=True)
    if semantic.returncode != 0:
        errors.append("goal-loop semantic validation failed")
        for line in (semantic.stdout + semantic.stderr).splitlines():
            if line.strip():
                errors.append(f"goal-loop: {line}")

    actual, checksum_errors = parse_checksums(ROOT / "CHECKSUMS.txt")
    errors.extend(checksum_errors)
    expected = expected_checksums()
    for rel in sorted(set(expected) - set(actual)):
        errors.append(f"CHECKSUMS.txt missing path: {rel}")
    for rel in sorted(set(actual) - set(expected)):
        errors.append(f"CHECKSUMS.txt unexpected path: {rel}")
    for rel in sorted(set(actual) & set(expected)):
        if actual[rel] != expected[rel]:
            errors.append(f"CHECKSUMS.txt stale hash: {rel}")

    if errors:
        print("AI layout validation: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("AI layout validation: PASS")
    print(f"- canonical skills: {len(EXPECTED_SKILLS)}")
    print(f"- synchronized goal-loop resource pairs: {len(PAIRED_RESOURCES)}")
    print("- canonical AEOS source path: .ai/project-sources/")
    print("- harness adapters: Claude, Codex, Grok")
    print("- GitHub-first exact-head and closeout controls: enforced")
    print("- checksum manifest: current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
