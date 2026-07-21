#!/usr/bin/env python3
"""Validate PR #319 governance contracts against an exact GitHub head identity."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any

import yaml

REQUIRED_PATHS = (
    ".ai/project-sources/00_AEOS_MASTER_INDEX.md",
    ".ai/project-sources/07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md",
    ".ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md",
    ".github/ISSUE_TEMPLATE/test-failure.yml",
    ".github/workflows/test-selection-governance.yml",
    "AGENTS.md",
    "AI_OPERATING_MANUAL.md",
    "CLAUDE.md",
    "docs/decisions/ADR-019-github-first-engineering-control-plane.md",
    "docs/decisions/DECISION-PROPORTIONAL-TEST-SELECTION-001.md",
    "docs/decisions/README.md",
    "docs/governance/README.md",
    "docs/governance/branch-worktree-lifecycle-policy.md",
    "docs/governance/test-failure-triage.md",
    "docs/implementation-plans/github-first-control-plane-migration.md",
    "docs/testing/forecasting-and-schedule-test-bundles.md",
    "docs/evidence/test-selection-policy/branch-registration.yaml",
    "docs/evidence/test-selection-policy/corrective-authorization.md",
    "scripts/test-safe.sh",
    "scripts/validate-test-selection-governance.py",
)

ALLOWED_CHANGED_PATHS = {
    ".ai/project-sources/00_AEOS_MASTER_INDEX.md",
    ".ai/project-sources/07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md",
    ".ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md",
    ".github/ISSUE_TEMPLATE/test-failure.yml",
    ".github/workflows/test-selection-governance.yml",
    "AGENTS.md",
    "AI_OPERATING_MANUAL.md",
    "CLAUDE.md",
    "docs/decisions/ADR-019-github-first-engineering-control-plane.md",
    "docs/decisions/DECISION-PROPORTIONAL-TEST-SELECTION-001.md",
    "docs/decisions/README.md",
    "docs/governance/README.md",
    "docs/governance/branch-worktree-lifecycle-policy.md",
    "docs/governance/test-failure-triage.md",
    "docs/implementation-plans/github-first-control-plane-migration.md",
    "docs/testing/forecasting-and-schedule-test-bundles.md",
    "docs/evidence/test-selection-policy/branch-registration.yaml",
    "docs/evidence/test-selection-policy/corrective-authorization.md",
    "scripts/test-safe.sh",
    "scripts/validate-test-selection-governance.py",
}

NORMAL_TRANSITIONS = {
    (None, "REGISTERED"),
    ("REGISTERED", "ACTIVE"),
    ("ACTIVE", "REVIEW_PENDING"),
    ("REVIEW_PENDING", "CHANGES_REQUESTED"),
    ("REVIEW_PENDING", "MERGED_PENDING_CLEANUP"),
    ("CHANGES_REQUESTED", "ACTIVE"),
    ("CHANGES_REQUESTED", "REVIEW_PENDING"),
    ("MERGED_PENDING_CLEANUP", "CLEANUP_VERIFIED"),
    ("MERGED_PENDING_CLEANUP", "RETAINED_BY_DECISION"),
    ("MERGED_PENDING_CLEANUP", "CLEANUP_BLOCKED"),
    ("CLEANUP_BLOCKED", "MERGED_PENDING_CLEANUP"),
    ("CLEANUP_BLOCKED", "RETAINED_BY_DECISION"),
    ("RETAINED_BY_DECISION", "MERGED_PENDING_CLEANUP"),
    ("RETAINED_BY_DECISION", "CLOSED"),
    ("CLEANUP_VERIFIED", "CLOSED"),
}


def fail(message: str) -> None:
    raise ValueError(message)


def read_text(root: Path, rel: str) -> str:
    path = root / rel
    if not path.is_file():
        fail(f"missing required path: {rel}")
    return path.read_text(encoding="utf-8-sig")


def parse_frontmatter(root: Path, rel: str) -> tuple[dict[str, Any], str]:
    text = read_text(root, rel)
    if not text.startswith("---\n"):
        fail(f"missing YAML front matter: {rel}")
    try:
        _, front, body = text.split("---", 2)
    except ValueError as exc:
        raise ValueError(f"invalid front matter boundary: {rel}") from exc
    data = yaml.safe_load(front)
    if not isinstance(data, dict):
        fail(f"front matter is not a mapping: {rel}")
    return data, body


def git_output(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=False
    )
    if proc.returncode != 0:
        fail(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def require_contains(text: str, needle: str, rel: str) -> None:
    if needle not in text:
        fail(f"{rel} missing required contract: {needle}")


def validate(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve()
    if not (root / ".git").exists():
        fail(f"not a Git checkout: {root}")

    head = git_output(root, "rev-parse", "HEAD")
    if head != args.github_head_sha:
        fail(f"checkout HEAD {head} does not match authenticated head {args.github_head_sha}")

    changed = [
        line
        for line in git_output(root, "diff", "--name-only", args.github_base_sha, head).splitlines()
        if line
    ]
    unexpected = sorted(set(changed) - ALLOWED_CHANGED_PATHS)
    if unexpected:
        fail(f"unauthorized changed paths: {unexpected}")

    for rel in REQUIRED_PATHS:
        read_text(root, rel)

    frontmatter_paths = (
        ".ai/project-sources/00_AEOS_MASTER_INDEX.md",
        ".ai/project-sources/07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md",
        ".ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md",
        "docs/decisions/ADR-019-github-first-engineering-control-plane.md",
        "docs/decisions/DECISION-PROPORTIONAL-TEST-SELECTION-001.md",
        "docs/governance/branch-worktree-lifecycle-policy.md",
        "docs/implementation-plans/github-first-control-plane-migration.md",
    )
    parsed_frontmatter = {rel: parse_frontmatter(root, rel)[0] for rel in frontmatter_paths}

    yaml_paths = (
        ".github/ISSUE_TEMPLATE/test-failure.yml",
        ".github/workflows/test-selection-governance.yml",
        "docs/evidence/test-selection-policy/branch-registration.yaml",
    )
    parsed_yaml: dict[str, Any] = {}
    for rel in yaml_paths:
        data = yaml.safe_load(read_text(root, rel))
        if not isinstance(data, dict):
            fail(f"YAML document is not a mapping: {rel}")
        parsed_yaml[rel] = data

    standard07 = read_text(root, ".ai/project-sources/07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md")
    standard11 = read_text(root, ".ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md")
    agents = read_text(root, "AGENTS.md")
    claude = read_text(root, "CLAUDE.md")
    testing = read_text(root, "docs/testing/forecasting-and-schedule-test-bundles.md")
    safe_script = read_text(root, "scripts/test-safe.sh")

    require_contains(standard07, "unmapped broad suite", "Standard 07")
    require_contains(standard07, "conflicts with Standard 11", "Standard 07")
    require_contains(standard07, "bash scripts/test-safe.sh", "Standard 07")
    require_contains(standard11, "bash scripts/test-safe.sh", "Standard 11")
    require_contains(standard11, "TF-<issue-number>", "Standard 11")
    require_contains(agents, ".ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md", "AGENTS.md")
    require_contains(claude, ".ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md", "CLAUDE.md")
    require_contains(testing, "bash scripts/test-safe.sh", "testing guide")
    require_contains(safe_script, "not integration and not manual and not live", "safe suite")
    require_contains(safe_script, "tests", "safe suite")
    require_contains(safe_script, "npm test", "safe suite")
    require_contains(safe_script, "unsupported argument", "safe suite")
    require_contains(safe_script, "cannot be combined with --frontend-only", "safe suite")

    branch_path = "docs/evidence/test-selection-policy/branch-registration.yaml"
    branch = parsed_yaml[branch_path]
    if branch.get("schema_version") != 2:
        fail("branch registration must use schema_version 2")
    if "branch_tip_sha" in branch or "candidate_head_sha" in branch:
        fail("self-referential branch_tip_sha/candidate_head_sha fields are prohibited")
    expected_branch_fields = {
        "registration_tip_sha",
        "current_tip_authority",
        "current_tip_recorded_in_repository",
        "review_candidate_binding",
    }
    missing = expected_branch_fields - set(branch)
    if missing:
        fail(f"branch registration missing fields: {sorted(missing)}")
    if branch["current_tip_authority"] != "authenticated_github":
        fail("current branch tip must resolve from authenticated GitHub")
    if branch["current_tip_recorded_in_repository"] is not False:
        fail("repository record must not claim to contain its current tip")
    if branch["review_candidate_binding"] != "external_exact_sha_review":
        fail("review candidate must be externally exact-SHA bound")
    if branch.get("base_sha") != args.github_base_sha:
        fail("branch registration base SHA mismatch")
    if branch.get("remote_branch") != args.branch_name:
        fail("branch registration branch name mismatch")
    if int(branch.get("pull_request")) != args.pr_number:
        fail("branch registration PR mismatch")

    transitions = branch.get("transitions")
    if not isinstance(transitions, list) or not transitions:
        fail("branch registration has no transitions")
    observed_state: str | None = None
    transition_ids: set[str] = set()
    for item in transitions:
        if not isinstance(item, dict):
            fail("transition is not a mapping")
        transition_id = item.get("transition_id")
        if not transition_id or transition_id in transition_ids:
            fail("transition IDs must be present and unique")
        transition_ids.add(transition_id)
        edge = (item.get("from_state"), item.get("to_state"))
        if edge not in NORMAL_TRANSITIONS:
            fail(f"invalid transition edge: {edge}")
        if item.get("from_state") != observed_state:
            fail(f"transition chain mismatch at {transition_id}")
        for field in ("occurred_at", "actor", "authorization_id", "evidence", "reason"):
            if not item.get(field):
                fail(f"transition {transition_id} missing {field}")
        observed_state = item.get("to_state")
    if observed_state != branch.get("lifecycle_state"):
        fail("final transition state does not match lifecycle_state")

    adr = parsed_frontmatter["docs/decisions/ADR-019-github-first-engineering-control-plane.md"]
    policy = parsed_frontmatter["docs/governance/branch-worktree-lifecycle-policy.md"]
    plan = parsed_frontmatter["docs/implementation-plans/github-first-control-plane-migration.md"]
    decision = parsed_frontmatter["docs/decisions/DECISION-PROPORTIONAL-TEST-SELECTION-001.md"]

    if adr.get("status") != "Accepted — Phase A":
        fail("ADR-019 status is not Accepted — Phase A")
    if policy.get("status") != "Accepted — Phase A":
        fail("POL-GIT-HYGIENE-001 status is not Accepted — Phase A")
    if plan.get("phase_b_authorized") is not False:
        fail("migration plan must state Phase B is not authorized")
    if "Review Pending" not in str(decision.get("status")):
        fail("proportional-testing decision must remain review pending")
    if not str(decision.get("acceptance_state", "")).startswith("NOT ACCEPTED"):
        fail("decision acceptance state must remain NOT ACCEPTED")

    supersedes = decision.get("supersedes")
    if not isinstance(supersedes, list) or not supersedes:
        fail("decision lacks exact permanent-identity supersession")
    target = supersedes[0]
    expected_target = {
        "title": "PI-WI-03-ARC-PLAN.md",
        "revision": 4,
        "drive_id": "1iPaw4yjgdXP_VvXb7XwNKn8gIiPyMWk_",
        "sha256": "419ef24a3139214b761ab682190adb23ce1147ae3ec6dbe344a2eda45a648a64",
    }
    for key, value in expected_target.items():
        if target.get(key) != value:
            fail(f"permanent-identity supersession mismatch for {key}")
    clauses = target.get("affected_clauses")
    expected_sections = {
        "Governance (AEOS) — role-separated, applies to EACH unit",
        "Verification (each unit)",
    }
    if not isinstance(clauses, list) or {
        item.get("section") for item in clauses if isinstance(item, dict)
    } != expected_sections:
        fail("permanent-identity supersession lacks exact affected clauses")

    issue_form = parsed_yaml[".github/ISSUE_TEMPLATE/test-failure.yml"]
    ids = {entry.get("id") for entry in issue_form.get("body", []) if isinstance(entry, dict)}
    required_issue_ids = {
        "source_work_item",
        "discovered_at",
        "failing_ids",
        "classification",
        "triage_owner",
        "evidence",
        "affected_gate",
        "current_disposition",
        "authorization_state",
        "corrective_identity",
        "closure_evidence",
    }
    if not required_issue_ids.issubset(ids):
        fail(f"test-failure issue form missing IDs: {sorted(required_issue_ids - ids)}")

    file_hashes = {
        rel: hashlib.sha256(read_text(root, rel).encode("utf-8")).hexdigest()
        for rel in REQUIRED_PATHS
    }
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "result": "PASS",
        "repository": "RMF112018/hb-personal-assistant",
        "pull_request": args.pr_number,
        "branch": args.branch_name,
        "base_sha": args.github_base_sha,
        "head_sha": head,
        "source": args.identity_source,
        "changed_files": changed,
        "checks": {
            "yaml_and_frontmatter": "PASS",
            "branch_transition_graph": "PASS",
            "external_tip_semantics": "PASS",
            "standard_07_11_consistency": "PASS",
            "safe_suite_contract": "PASS",
            "durable_failure_ownership": "PASS",
            "authority_statuses": "PASS",
            "permanent_identity_traceability": "PASS",
            "authorized_diff_scope": "PASS",
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "github_actions": os.environ.get("GITHUB_ACTIONS") == "true",
        },
        "file_sha256": file_hashes,
    }
    canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    receipt["evidence_sha256"] = hashlib.sha256(canonical).hexdigest()
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--github-head-sha", required=True)
    parser.add_argument("--github-base-sha", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--branch-name", required=True)
    parser.add_argument("--identity-source", default="authenticated-github")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        receipt = validate(args)
    except Exception as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
