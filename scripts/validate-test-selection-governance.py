#!/usr/bin/env python3
"""Validate PR #319 governance contracts and exact-head evidence."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import tomllib
from typing import Any, Callable

import yaml

REPOSITORY = "RMF112018/hb-personal-assistant"
COLLECTION_COMMAND = [
    "bash",
    "scripts/test-safe.sh",
    "--collect-only",
    "--python-only",
]

REQUIRED_READ_PATHS = (
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
    "pyproject.toml",
    "subrepos/construction-financial-review/pyproject.toml",
    "frontend/package.json",
)

AUTHORIZED_CHANGED_PATHS = {
    ".ai/project-sources/00_AEOS_MASTER_INDEX.md",
    ".ai/project-sources/07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md",
    ".ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md",
    ".github/ISSUE_TEMPLATE/test-failure.yml",
    ".github/workflows/test-selection-governance.yml",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/decisions/ADR-019-github-first-engineering-control-plane.md",
    "docs/decisions/DECISION-PROPORTIONAL-TEST-SELECTION-001.md",
    "docs/decisions/README.md",
    "docs/evidence/test-selection-policy/branch-registration.yaml",
    "docs/evidence/test-selection-policy/corrective-authorization.md",
    "docs/governance/README.md",
    "docs/governance/branch-worktree-lifecycle-policy.md",
    "docs/governance/test-failure-triage.md",
    "docs/implementation-plans/github-first-control-plane-migration.md",
    "docs/testing/forecasting-and-schedule-test-bundles.md",
    "scripts/test-safe.sh",
    "scripts/validate-test-selection-governance.py",
}

EXPECTED_FRONTMATTER_PATHS = {
    ".ai/project-sources/00_AEOS_MASTER_INDEX.md",
    ".ai/project-sources/07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md",
    ".ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md",
    "docs/decisions/ADR-019-github-first-engineering-control-plane.md",
    "docs/decisions/DECISION-PROPORTIONAL-TEST-SELECTION-001.md",
    "docs/governance/branch-worktree-lifecycle-policy.md",
    "docs/implementation-plans/github-first-control-plane-migration.md",
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

REQUIRED_ISSUE_IDS = {
    "source_work_item",
    "discovered_at",
    "candidate_sha",
    "command",
    "environment",
    "failing_ids",
    "classification",
    "triage_owner",
    "base_evidence",
    "affected_gate",
    "current_disposition",
    "authorization_state",
    "corrective_identity",
    "review_result",
    "integrated_candidate_result",
    "closure_evidence",
}

DISCOVERY_REQUIRED_ISSUE_IDS = {
    "source_work_item",
    "discovered_at",
    "candidate_sha",
    "command",
    "environment",
    "failing_ids",
    "classification",
    "triage_owner",
    "base_evidence",
    "affected_gate",
    "current_disposition",
    "authorization_state",
}

DEPENDENCY_MODULES = ("pytest", "mcp", "fastapi", "numpy", "scipy")

COLLECTION_SUMMARY = re.compile(
    r"(?P<selected>\d+)/(?P<total>\d+) tests collected "
    r"\((?P<deselected>\d+) deselected\)"
)


def fail(message: str) -> None:
    raise ValueError(message)


def read_text(root: Path, rel: str) -> str:
    path = root / rel
    if not path.is_file():
        fail(f"missing required path: {rel}")
    return path.read_text(encoding="utf-8-sig")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        fail(f"missing evidence file: {path}")
    return sha256_bytes(path.read_bytes())


def read_exit_code(path: Path, label: str) -> int:
    if not path.is_file():
        fail(f"missing {label} exit-code file: {path}")
    raw = path.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"-?\d+", raw):
        fail(f"invalid {label} exit-code value: {raw!r}")
    return int(raw)


def parse_frontmatter_text(text: str, rel: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        fail(f"missing YAML front matter: {rel}")
    end = text.find("\n---\n", 4)
    if end < 0:
        fail(f"invalid front matter boundary: {rel}")
    front = text[4:end]
    body = text[end + 5 :]
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


def expect_failure(
    action: Callable[[], None], label: str, diagnostic: str | None = None
) -> None:
    try:
        action()
    except ValueError as exc:
        if diagnostic is not None and diagnostic not in str(exc):
            fail(
                f"negative fixture {label} failed with wrong diagnostic: {exc}; "
                f"expected substring {diagnostic!r}"
            )
        return
    fail(f"negative validation fixture unexpectedly passed: {label}")


def validate_changed_paths(changed: set[str]) -> None:
    unexpected = sorted(changed - AUTHORIZED_CHANGED_PATHS)
    missing = sorted(AUTHORIZED_CHANGED_PATHS - changed)
    if unexpected or missing:
        parts: list[str] = []
        if unexpected:
            parts.append(f"unexpected={unexpected}")
        if missing:
            parts.append(f"missing={missing}")
        fail("authorized changed-path set mismatch: " + "; ".join(parts))


def validate_issue_form(issue_form: Any) -> None:
    if not isinstance(issue_form, dict):
        fail("test-failure issue form is not a mapping")
    if "about" in issue_form:
        fail("GitHub issue forms use top-level description, not about")
    required_top = {"name", "description", "body"}
    missing_top = required_top - set(issue_form)
    if missing_top:
        fail(f"test-failure issue form missing top-level fields: {sorted(missing_top)}")
    for field in ("name", "description"):
        value = issue_form.get(field)
        if not isinstance(value, str) or not value.strip():
            fail(f"test-failure issue form {field} must be a non-empty string")
    labels = issue_form.get("labels", [])
    if not isinstance(labels, list) or any(not isinstance(item, str) for item in labels):
        fail("test-failure issue form labels must be a list of strings")
    body = issue_form.get("body")
    if not isinstance(body, list) or not body:
        fail("test-failure issue form body must be a non-empty list")

    ids: set[str] = set()
    required_by_id: dict[str, bool] = {}
    for index, entry in enumerate(body):
        if not isinstance(entry, dict):
            fail(f"issue-form body entry {index} is not a mapping")
        field_type = entry.get("type")
        if field_type not in {"markdown", "input", "textarea", "dropdown", "checkboxes"}:
            fail(f"issue-form body entry {index} has unsupported type: {field_type}")
        attributes = entry.get("attributes")
        if not isinstance(attributes, dict):
            fail(f"issue-form body entry {index} lacks attributes mapping")
        if field_type == "markdown":
            if not isinstance(attributes.get("value"), str) or not attributes["value"].strip():
                fail(f"issue-form markdown entry {index} lacks value")
            continue

        field_id = entry.get("id")
        if not isinstance(field_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", field_id):
            fail(f"issue-form entry {index} has invalid id")
        if field_id in ids:
            fail(f"issue-form duplicate id: {field_id}")
        ids.add(field_id)
        if not isinstance(attributes.get("label"), str) or not attributes["label"].strip():
            fail(f"issue-form field {field_id} lacks label")
        if field_type == "dropdown":
            options = attributes.get("options")
            if not isinstance(options, list) or len(options) < 2 or any(
                not isinstance(option, str) or not option.strip() for option in options
            ):
                fail(f"issue-form dropdown {field_id} requires at least two string options")
            if len(set(options)) != len(options):
                fail(f"issue-form dropdown {field_id} options must be distinct")
        validations = entry.get("validations", {})
        if not isinstance(validations, dict):
            fail(f"issue-form field {field_id} validations must be a mapping")
        required = validations.get("required", False)
        if not isinstance(required, bool):
            fail(f"issue-form field {field_id} required must be boolean")
        required_by_id[field_id] = required

    missing_ids = REQUIRED_ISSUE_IDS - ids
    if missing_ids:
        fail(f"test-failure issue form missing IDs: {sorted(missing_ids)}")
    not_required = sorted(
        field_id for field_id in DISCOVERY_REQUIRED_ISSUE_IDS if not required_by_id.get(field_id)
    )
    if not_required:
        fail(f"discovery-time issue fields must be required: {not_required}")


def run_issue_form_negative_fixtures(issue_form: dict[str, Any]) -> None:
    missing_description = copy.deepcopy(issue_form)
    missing_description.pop("description", None)
    expect_failure(
        lambda: validate_issue_form(missing_description),
        "issue form missing description",
        "missing top-level fields",
    )

    legacy_about = copy.deepcopy(issue_form)
    legacy_about["about"] = legacy_about.pop("description")
    expect_failure(
        lambda: validate_issue_form(legacy_about),
        "issue form legacy about key",
        "description, not about",
    )

    duplicate = copy.deepcopy(issue_form)
    editable = [entry for entry in duplicate["body"] if entry.get("id")]
    editable[1]["id"] = editable[0]["id"]
    expect_failure(
        lambda: validate_issue_form(duplicate),
        "issue form duplicate ID",
        "duplicate id",
    )

    missing_discovery = copy.deepcopy(issue_form)
    missing_discovery["body"] = [
        entry for entry in missing_discovery["body"] if entry.get("id") != "candidate_sha"
    ]
    expect_failure(
        lambda: validate_issue_form(missing_discovery),
        "issue form missing discovery field",
        "missing IDs",
    )

    malformed_dropdown = copy.deepcopy(issue_form)
    classification = next(
        entry for entry in malformed_dropdown["body"] if entry.get("id") == "classification"
    )
    classification["attributes"]["options"] = ["ONLY_ONE"]
    expect_failure(
        lambda: validate_issue_form(malformed_dropdown),
        "issue form malformed dropdown",
        "at least two string options",
    )

    duplicate_dropdown = copy.deepcopy(issue_form)
    classification = next(
        entry for entry in duplicate_dropdown["body"] if entry.get("id") == "classification"
    )
    first = classification["attributes"]["options"][0]
    classification["attributes"]["options"] = [first, first]
    expect_failure(
        lambda: validate_issue_form(duplicate_dropdown),
        "issue form duplicate dropdown option",
        "options must be distinct",
    )


def run_probe(
    root: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "scripts/test-safe.sh", *args],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def require_probe_result(
    proc: subprocess.CompletedProcess[str], expected_code: int, needle: str, label: str
) -> None:
    combined = proc.stdout + proc.stderr
    if proc.returncode != expected_code or needle not in combined:
        fail(
            f"safe-suite probe {label} failed: code={proc.returncode}, "
            f"expected={expected_code}, output={combined!r}"
        )


def validate_safe_suite_static(safe_script: str) -> None:
    for forbidden in ("/Users/", "/home/", "C:\\Users\\"):
        if forbidden in safe_script:
            fail(f"safe suite contains operator-specific absolute path: {forbidden}")

    generic_patterns = (
        r"PYTHON_BIN\s*=\s*['\"]python3?['\"]",
        r"candidate\s*=\s*['\"]python3?['\"]",
        r"\$\{PYTHON:-\s*python3?\}",
        r"command\s+-v(?:\s+--)?\s+['\"]?python3?['\"]?",
    )
    for pattern in generic_patterns:
        if re.search(pattern, safe_script):
            fail(f"safe suite contains generic interpreter fallback pattern: {pattern}")

    required_tokens = (
        'candidate="$ROOT/.venv/bin/python"',
        "Python 3.12 or newer",
        "import pytest, mcp, fastapi, numpy, scipy",
        "not integration and not manual and not live",
        'export PYTHONPATH="$ROOT/src:$ROOT/subrepos/construction-financial-review/src',
        "npm test",
        "unsupported argument",
        "cannot be combined with --frontend-only",
    )
    for token in required_tokens:
        require_contains(safe_script, token, "safe suite")


def run_safe_suite_static_negative_fixtures(safe_script: str) -> None:
    direct_default = safe_script.replace(
        'candidate="$ROOT/.venv/bin/python"', 'candidate="${PYTHON:-python}"', 1
    )
    expect_failure(
        lambda: validate_safe_suite_static(direct_default),
        "alternate generic default expansion",
        "generic interpreter fallback",
    )

    command_lookup = safe_script.replace(
        'candidate="$ROOT/.venv/bin/python"', 'candidate="$(command -v python)"', 1
    )
    expect_failure(
        lambda: validate_safe_suite_static(command_lookup),
        "alternate generic command lookup",
        "generic interpreter fallback",
    )


def write_fake_interpreter(path: Path, mode: str) -> None:
    script = f'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import re
import sys
args = sys.argv[1:]
mode = {mode!r}
if args[:1] == ['-c']:
    code = args[1] if len(args) > 1 else ''
    if 'sys.version_info' in code:
        raise SystemExit(1 if mode == 'old' else 0)
    match = re.search(r'import\\s+([A-Za-z0-9_, ]+)', code)
    if match:
        modules = [item.strip() for item in match.group(1).split(',') if item.strip()]
        missing = mode.removeprefix('missing_') if mode.startswith('missing_') else None
        payload = {{'mode': mode, 'modules': modules, 'missing': missing, 'pytest_invoked': False}}
        log = os.environ.get('SAFE_SUITE_PROBE_LOG')
        if log:
            Path(log).write_text(json.dumps(payload), encoding='utf-8')
        if missing and missing in modules:
            raise SystemExit(1)
        raise SystemExit(0)
    raise SystemExit(8)
if args[:2] == ['-m', 'pytest']:
    log = os.environ.get('SAFE_SUITE_PROBE_LOG')
    if log:
        Path(log).write_text(json.dumps({{'mode': mode, 'pytest_args': args, 'pytest_invoked': True}}), encoding='utf-8')
    raise SystemExit(0 if mode == 'good' else 7)
raise SystemExit(9)
'''
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def validate_safe_suite_probes(root: Path) -> None:
    base_env = os.environ.copy()
    invalid_arg = run_probe(root, "tests/test_example.py", env=base_env)
    require_probe_result(invalid_arg, 2, "unsupported argument", "arbitrary target")

    no_component = run_probe(root, "--python-only", "--frontend-only", env=base_env)
    require_probe_result(no_component, 2, "no suite component selected", "contradictory modes")

    bad_collect = run_probe(root, "--collect-only", "--frontend-only", env=base_env)
    require_probe_result(
        bad_collect, 2, "cannot be combined with --frontend-only", "frontend collect-only"
    )

    missing_env = base_env | {"PYTHON": "/definitely/not/a/python/executable"}
    missing = run_probe(root, "--collect-only", "--python-only", env=missing_env)
    require_probe_result(missing, 3, "no compliant Python interpreter", "missing interpreter")

    spaced_env = base_env | {"PYTHON": "python -O"}
    spaced = run_probe(root, "--collect-only", "--python-only", env=spaced_env)
    require_probe_result(spaced, 3, "exactly one executable", "interpreter arguments")

    with tempfile.TemporaryDirectory(prefix="pr319-safe-suite-") as tmp:
        temp = Path(tmp)
        log_path = temp / "probe.json"

        good = temp / "python-good"
        write_fake_interpreter(good, "good")
        good_env = base_env | {
            "PYTHON": str(good),
            "SAFE_SUITE_PROBE_LOG": str(log_path),
        }
        good_run = run_probe(root, "--collect-only", "--python-only", env=good_env)
        if good_run.returncode != 0:
            fail(f"safe-suite compliant interpreter probe failed: {good_run.stderr}")
        observed_payload = json.loads(log_path.read_text(encoding="utf-8"))
        observed = observed_payload.get("pytest_args")
        expected = [
            "-m",
            "pytest",
            "-m",
            "not integration and not manual and not live",
            "tests",
            "--collect-only",
        ]
        if observed != expected or observed_payload.get("pytest_invoked") is not True:
            fail(f"safe-suite pytest arguments differ: {observed_payload}")

        old = temp / "python-old"
        write_fake_interpreter(old, "old")
        old_run = run_probe(
            root,
            "--collect-only",
            "--python-only",
            env=base_env | {"PYTHON": str(old)},
        )
        require_probe_result(old_run, 3, "Python 3.12 or newer", "old interpreter")

        for module in DEPENDENCY_MODULES:
            module_log = temp / f"probe-missing-{module}.json"
            fake = temp / f"python-missing-{module}"
            write_fake_interpreter(fake, f"missing_{module}")
            probe_env = base_env | {
                "PYTHON": str(fake),
                "SAFE_SUITE_PROBE_LOG": str(module_log),
            }
            proc = run_probe(root, "--collect-only", "--python-only", env=probe_env)
            require_probe_result(
                proc,
                3,
                "Python dependencies are unavailable",
                f"missing dependency {module}",
            )
            payload = json.loads(module_log.read_text(encoding="utf-8"))
            if payload.get("mode") != f"missing_{module}":
                fail(f"dependency probe {module} recorded wrong mode: {payload}")
            if module not in payload.get("modules", []):
                fail(f"dependency probe {module} did not observe required import: {payload}")
            if payload.get("missing") != module:
                fail(f"dependency probe {module} did not isolate the named module: {payload}")
            if payload.get("pytest_invoked") is not False:
                fail(f"dependency probe {module} unexpectedly invoked pytest: {payload}")


def normalize_requirement_name(requirement: Any) -> str | None:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", str(requirement))
    if not match:
        return None
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()


def validate_dependency_declarations(root_toml: bytes, subrepo_toml: bytes) -> None:
    root_data = tomllib.loads(root_toml.decode("utf-8"))
    subrepo_data = tomllib.loads(subrepo_toml.decode("utf-8"))
    extras = root_data.get("project", {}).get("optional-dependencies", {})
    required_extras = {"dev": "pytest", "mcp": "mcp", "analytics-ui": "fastapi"}
    for extra, package in required_extras.items():
        values = extras.get(extra)
        names = {normalize_requirement_name(item) for item in values or []}
        if not isinstance(values, list) or package not in names:
            fail(f"root optional dependency {extra} does not declare {package}")
    subdeps = subrepo_data.get("project", {}).get("dependencies", [])
    subnames = {normalize_requirement_name(item) for item in subdeps or []}
    for package in ("numpy", "scipy"):
        if not isinstance(subdeps, list) or package not in subnames:
            fail(f"construction subrepository does not declare {package}")


def parse_collection_log(text: str) -> dict[str, int]:
    matches = list(COLLECTION_SUMMARY.finditer(text))
    if not matches:
        fail("collection log lacks selected/total/deselected summary")
    match = matches[-1]
    selected = int(match.group("selected"))
    total = int(match.group("total"))
    deselected = int(match.group("deselected"))
    if selected + deselected != total:
        fail("collection summary counts are inconsistent")
    return {
        "selected_tests": selected,
        "total_tests": total,
        "deselected_tests": deselected,
        "collection_errors": 0,
        "application_tests_executed": 0,
    }


def compute_evidence_hash(receipt: dict[str, Any]) -> str:
    clean = copy.deepcopy(receipt)
    clean.pop("evidence_sha256", None)
    canonical = json.dumps(clean, sort_keys=True, separators=(",", ":")).encode()
    return sha256_bytes(canonical)


def validate_branch_registration(branch: dict[str, Any], args: argparse.Namespace) -> None:
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
    if observed_state != "REVIEW_PENDING":
        fail("PR #319 branch must be REVIEW_PENDING for exact-head re-review")


def validate_repository(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve()
    if not (root / ".git").exists():
        fail(f"not a Git checkout: {root}")

    head = git_output(root, "rev-parse", "HEAD")
    if head != args.github_head_sha:
        fail(f"checkout HEAD {head} does not match authenticated head {args.github_head_sha}")

    changed_list = [
        line
        for line in git_output(root, "diff", "--name-only", args.github_base_sha, head).splitlines()
        if line
    ]
    changed_set = set(changed_list)
    validate_changed_paths(changed_set)
    expect_failure(
        lambda: validate_changed_paths(changed_set | {"AI_OPERATING_MANUAL.md"}),
        "extra changed path",
        "unexpected",
    )
    known_changed = next(iter(sorted(AUTHORIZED_CHANGED_PATHS)))
    expect_failure(
        lambda: validate_changed_paths(changed_set - {known_changed}),
        "missing changed path",
        "missing",
    )

    texts = {rel: read_text(root, rel) for rel in REQUIRED_READ_PATHS}

    parsed_frontmatter: dict[str, dict[str, Any]] = {}
    detected_frontmatter: set[str] = set()
    for rel, text in texts.items():
        if rel.endswith(".md") and text.startswith("---\n"):
            detected_frontmatter.add(rel)
            parsed_frontmatter[rel] = parse_frontmatter_text(text, rel)[0]
    missing_frontmatter = EXPECTED_FRONTMATTER_PATHS - detected_frontmatter
    if missing_frontmatter:
        fail(f"expected governed front matter missing: {sorted(missing_frontmatter)}")

    parsed_yaml: dict[str, dict[str, Any]] = {}
    yaml_paths = sorted(rel for rel in REQUIRED_READ_PATHS if rel.endswith((".yml", ".yaml")))
    for rel in yaml_paths:
        data = yaml.safe_load(texts[rel])
        if not isinstance(data, dict):
            fail(f"YAML document is not a mapping: {rel}")
        parsed_yaml[rel] = data

    standard07 = texts[".ai/project-sources/07_AEOS_LOCAL_AGENT_OPERATING_CONTRACT.md"]
    standard11 = texts[".ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md"]
    agents = texts["AGENTS.md"]
    claude = texts["CLAUDE.md"]
    testing = texts["docs/testing/forecasting-and-schedule-test-bundles.md"]
    safe_script = texts["scripts/test-safe.sh"]
    workflow = texts[".github/workflows/test-selection-governance.yml"]

    require_contains(standard07, "unmapped broad suite", "Standard 07")
    require_contains(standard07, "conflicts with Standard 11", "Standard 07")
    require_contains(standard07, "bash scripts/test-safe.sh", "Standard 07")
    require_contains(standard11, "bash scripts/test-safe.sh", "Standard 11")
    require_contains(standard11, "TF-<issue-number>", "Standard 11")
    require_contains(
        agents,
        ".ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md",
        "AGENTS.md",
    )
    require_contains(
        claude,
        ".ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md",
        "CLAUDE.md",
    )
    require_contains(testing, "bash scripts/test-safe.sh", "testing guide")

    validate_safe_suite_static(safe_script)
    run_safe_suite_static_negative_fixtures(safe_script)
    validate_safe_suite_probes(root)
    validate_dependency_declarations(
        (root / "pyproject.toml").read_bytes(),
        (root / "subrepos/construction-financial-review/pyproject.toml").read_bytes(),
    )

    workflow_tokens = (
        "ref: ${{ github.event.pull_request.head.sha }}",
        "python-version: '3.12'",
        "python -m pip install -e '.[dev]'",
        "bash scripts/test-safe.sh --collect-only --python-only",
        "validate --github-head-sha '${{ github.event.pull_request.head.sha }}'",
        "finalize-receipt",
        "verify-receipt",
        "--expected-repository 'RMF112018/hb-personal-assistant'",
        "--expected-pr-number '${{ github.event.pull_request.number }}'",
        "--expected-branch '${{ github.event.pull_request.head.ref }}'",
        "--expected-base-sha '${{ github.event.pull_request.base.sha }}'",
        "--expected-head-sha '${{ github.event.pull_request.head.sha }}'",
        "--expected-identity-source 'github-actions-pull-request-event'",
        "pr319-safe-collection.exitcode",
        "pr319-governance-validator.exitcode",
    )
    for token in workflow_tokens:
        require_contains(workflow, token, "governance workflow")

    branch = parsed_yaml["docs/evidence/test-selection-policy/branch-registration.yaml"]
    validate_branch_registration(branch, args)

    adr = parsed_frontmatter[
        "docs/decisions/ADR-019-github-first-engineering-control-plane.md"
    ]
    policy = parsed_frontmatter[
        "docs/governance/branch-worktree-lifecycle-policy.md"
    ]
    plan = parsed_frontmatter[
        "docs/implementation-plans/github-first-control-plane-migration.md"
    ]
    decision = parsed_frontmatter[
        "docs/decisions/DECISION-PROPORTIONAL-TEST-SELECTION-001.md"
    ]
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
    validate_issue_form(issue_form)
    run_issue_form_negative_fixtures(issue_form)

    collection_log_path = (root / args.collection_log).resolve()
    collection_exit_path = (root / args.collection_exitcode_file).resolve()
    collection_exit = read_exit_code(collection_exit_path, "collection")
    if collection_exit != 0:
        fail(f"bounded collection exit code is {collection_exit}, expected 0")
    collection_text = collection_log_path.read_text(encoding="utf-8", errors="replace")
    collection_counts = parse_collection_log(collection_text)

    observed_hashes = {
        rel: sha256_bytes(text.encode("utf-8")) for rel, text in texts.items()
    }
    invocation = [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]]
    receipt: dict[str, Any] = {
        "schema_version": 2,
        "result": "PASS",
        "repository": REPOSITORY,
        "pull_request": args.pr_number,
        "branch": args.branch_name,
        "base_sha": args.github_base_sha,
        "head_sha": head,
        "identity_source": args.identity_source,
        "changed_files": sorted(changed_set),
        "authorized_changed_paths": sorted(AUTHORIZED_CHANGED_PATHS),
        "collection": {
            "command": COLLECTION_COMMAND,
            "exit_code": collection_exit,
            **collection_counts,
            "log_file": args.collection_log,
            "log_sha256": sha256_file(collection_log_path),
            "exitcode_file": args.collection_exitcode_file,
            "exitcode_file_sha256": sha256_file(collection_exit_path),
        },
        "validator": {
            "command": invocation,
            "exit_code": 0,
            "log_file": args.validator_log_name,
            "log_sha256": None,
            "exitcode_file": args.validator_exitcode_name,
            "exitcode_file_sha256": None,
        },
        "checks": {
            "yaml_and_frontmatter_inventory": "PASS",
            "branch_transition_graph": "PASS",
            "external_tip_semantics": "PASS",
            "standard_07_11_consistency": "PASS",
            "safe_suite_static_contract": "PASS",
            "safe_suite_static_negative_fixtures": "PASS",
            "safe_suite_adversarial_probes": "PASS",
            "safe_suite_individual_dependency_probes": "PASS",
            "safe_suite_dependency_declarations": "PASS",
            "issue_form_schema": "PASS",
            "issue_form_negative_fixtures": "PASS",
            "authority_statuses": "PASS",
            "permanent_identity_traceability": "PASS",
            "authorized_diff_scope_exact": "PASS",
            "authorized_diff_scope_negative_fixtures": "PASS",
            "workflow_exact_head_collection_and_receipt_contract": "PASS",
        },
        "environment": {
            "python": sys.version.split()[0],
            "python_executable": sys.executable,
            "platform": platform.platform(),
            "github_actions": os.environ.get("GITHUB_ACTIONS") == "true",
        },
        "hash_scope": {
            "repository_sources": "observed UTF-8 source bytes at the exact validated head; not an external expected-hash manifest",
            "artifact_evidence": "stored raw bytes for collection and validator logs and exit-code files",
        },
        "observed_file_sha256": observed_hashes,
    }
    receipt["evidence_sha256"] = compute_evidence_hash(receipt)
    return receipt


def finalize_receipt(args: argparse.Namespace) -> dict[str, Any]:
    input_path = Path(args.input).resolve()
    receipt = json.loads(input_path.read_text(encoding="utf-8"))
    if receipt.get("schema_version") != 2 or receipt.get("result") != "PASS":
        fail("partial receipt is not a schema-2 PASS receipt")

    validator_log = Path(args.validator_log).resolve()
    validator_exit_path = Path(args.validator_exitcode_file).resolve()
    validator_exit = read_exit_code(validator_exit_path, "validator")
    if validator_exit != 0:
        fail(f"validator exit code is {validator_exit}, expected 0")

    validator = receipt.get("validator")
    if not isinstance(validator, dict):
        fail("partial receipt lacks validator section")
    if validator.get("exit_code") != validator_exit:
        fail("partial receipt validator exit code does not match captured file")
    validator["log_file"] = args.validator_log
    validator["log_sha256"] = sha256_file(validator_log)
    validator["exitcode_file"] = args.validator_exitcode_file
    validator["exitcode_file_sha256"] = sha256_file(validator_exit_path)

    receipt["finalizer"] = {
        "command": [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
        "exit_code": 0,
    }
    receipt["evidence_sha256"] = compute_evidence_hash(receipt)
    return receipt


def expected_validator_command(args: argparse.Namespace) -> list[str]:
    return [
        sys.executable,
        str(Path(__file__).resolve()),
        "validate",
        "--github-head-sha",
        args.expected_head_sha,
        "--github-base-sha",
        args.expected_base_sha,
        "--pr-number",
        str(args.expected_pr_number),
        "--branch-name",
        args.expected_branch,
        "--identity-source",
        args.expected_identity_source,
        "--collection-log",
        args.collection_log,
        "--collection-exitcode-file",
        args.collection_exitcode_file,
        "--validator-log-name",
        args.validator_log,
        "--validator-exitcode-name",
        args.validator_exitcode_file,
        "--output",
        args.partial_receipt,
    ]


def expected_finalizer_command(args: argparse.Namespace) -> list[str]:
    return [
        sys.executable,
        str(Path(__file__).resolve()),
        "finalize-receipt",
        "--input",
        args.partial_receipt,
        "--output",
        args.receipt,
        "--validator-log",
        args.validator_log,
        "--validator-exitcode-file",
        args.validator_exitcode_file,
    ]


def validate_exact_path_array(receipt: dict[str, Any], field: str) -> None:
    value = receipt.get(field)
    expected = sorted(AUTHORIZED_CHANGED_PATHS)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        fail(f"receipt {field} must be a list of strings")
    if len(value) != len(set(value)):
        fail(f"receipt {field} contains duplicate entries")
    if value != expected:
        fail(f"receipt {field} does not equal exact sorted authorized paths")


def expected_checks_payload() -> dict[str, str]:
    return {
        "yaml_and_frontmatter_inventory": "PASS",
        "branch_transition_graph": "PASS",
        "external_tip_semantics": "PASS",
        "standard_07_11_consistency": "PASS",
        "safe_suite_static_contract": "PASS",
        "safe_suite_static_negative_fixtures": "PASS",
        "safe_suite_adversarial_probes": "PASS",
        "safe_suite_individual_dependency_probes": "PASS",
        "safe_suite_dependency_declarations": "PASS",
        "issue_form_schema": "PASS",
        "issue_form_negative_fixtures": "PASS",
        "authority_statuses": "PASS",
        "permanent_identity_traceability": "PASS",
        "authorized_diff_scope_exact": "PASS",
        "authorized_diff_scope_negative_fixtures": "PASS",
        "workflow_exact_head_collection_and_receipt_contract": "PASS",
    }


def expected_environment_payload() -> dict[str, Any]:
    return {
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "github_actions": os.environ.get("GITHUB_ACTIONS") == "true",
    }


def expected_hash_scope_payload() -> dict[str, str]:
    return {
        "repository_sources": "observed UTF-8 source bytes at the exact validated head; not an external expected-hash manifest",
        "artifact_evidence": "stored raw bytes for collection and validator logs and exit-code files",
    }


def expected_observed_file_hashes(args: argparse.Namespace) -> dict[str, str]:
    root = Path(getattr(args, "repo_root", ".")).resolve()
    if not (root / ".git").exists():
        fail(f"not a Git checkout: {root}")
    head = git_output(root, "rev-parse", "HEAD")
    if head != args.expected_head_sha:
        fail(
            f"receipt verification checkout HEAD {head} does not match authenticated head "
            f"{args.expected_head_sha}"
        )
    texts = {rel: read_text(root, rel) for rel in REQUIRED_READ_PATHS}
    return {rel: sha256_bytes(text.encode("utf-8")) for rel, text in texts.items()}


def require_exact_keys(mapping: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(mapping, dict):
        fail(f"{label} must be a mapping")
    observed = set(mapping)
    if observed != expected:
        fail(
            f"{label} keys mismatch: unexpected={sorted(observed - expected)}; "
            f"missing={sorted(expected - observed)}"
        )
    return mapping


def validate_receipt_claims(
    receipt: dict[str, Any], args: argparse.Namespace, *, provisional: bool
) -> None:
    label = "provisional" if provisional else "final"
    expected_hash = compute_evidence_hash(receipt)
    if receipt.get("evidence_sha256") != expected_hash:
        if provisional:
            fail("partial receipt evidence SHA-256 mismatch")
        fail("receipt evidence SHA-256 mismatch")
    if receipt.get("schema_version") != 2 or receipt.get("result") != "PASS":
        if provisional:
            fail("partial receipt is not schema-2 PASS")
        fail("final receipt is not schema-2 PASS")
    if provisional and "finalizer" in receipt:
        fail("provisional receipt must not contain finalizer")

    top_level = {
        "schema_version",
        "result",
        "repository",
        "pull_request",
        "branch",
        "base_sha",
        "head_sha",
        "identity_source",
        "changed_files",
        "authorized_changed_paths",
        "collection",
        "validator",
        "checks",
        "environment",
        "hash_scope",
        "observed_file_sha256",
        "evidence_sha256",
    }
    if not provisional:
        top_level.add("finalizer")
    require_exact_keys(receipt, top_level, f"{label} receipt top-level fields")

    expected_identity = {
        "repository": args.expected_repository,
        "pull_request": args.expected_pr_number,
        "branch": args.expected_branch,
        "base_sha": args.expected_base_sha,
        "head_sha": args.expected_head_sha,
        "identity_source": args.expected_identity_source,
    }
    for field, expected in expected_identity.items():
        if receipt.get(field) != expected:
            fail(f"{label} receipt authenticated identity mismatch for {field}")

    collection = require_exact_keys(
        receipt.get("collection"),
        {
            "command",
            "exit_code",
            "selected_tests",
            "total_tests",
            "deselected_tests",
            "collection_errors",
            "application_tests_executed",
            "log_file",
            "log_sha256",
            "exitcode_file",
            "exitcode_file_sha256",
        },
        f"{label} receipt collection",
    )
    validator = require_exact_keys(
        receipt.get("validator"),
        {
            "command",
            "exit_code",
            "log_file",
            "log_sha256",
            "exitcode_file",
            "exitcode_file_sha256",
        },
        f"{label} receipt validator",
    )
    if collection.get("command") != COLLECTION_COMMAND:
        fail(f"{label} receipt collection command mismatch")
    if validator.get("command") != expected_validator_command(args):
        fail(f"{label} receipt validator command mismatch")
    if collection.get("application_tests_executed") != 0:
        fail(f"{label} receipt must record zero application tests executed")

    expected_references = (
        (collection, "collection.log_file", "log_file", args.collection_log),
        (
            collection,
            "collection.exitcode_file",
            "exitcode_file",
            args.collection_exitcode_file,
        ),
        (validator, "validator.log_file", "log_file", args.validator_log),
        (
            validator,
            "validator.exitcode_file",
            "exitcode_file",
            args.validator_exitcode_file,
        ),
    )
    for section, qualified, field, expected in expected_references:
        if section.get(field) != expected:
            fail(f"{label} receipt evidence-file reference mismatch for {qualified}")

    collection_log = Path(args.collection_log).resolve()
    collection_exit_path = Path(args.collection_exitcode_file).resolve()
    validator_log = Path(args.validator_log).resolve()
    validator_exit_path = Path(args.validator_exitcode_file).resolve()

    collection_exit = read_exit_code(collection_exit_path, "collection")
    validator_exit = read_exit_code(validator_exit_path, "validator")
    if collection_exit != 0 or validator_exit != 0:
        fail("captured collection and validator exit codes must both be zero")
    if collection.get("exit_code") != collection_exit:
        fail(f"{label} receipt collection exit code mismatch")
    if validator.get("exit_code") != validator_exit:
        fail(f"{label} receipt validator exit code mismatch")

    collection_evidence = (
        ("log_sha256", collection_log),
        ("exitcode_file_sha256", collection_exit_path),
    )
    for key, path in collection_evidence:
        if collection.get(key) != sha256_file(path):
            fail(f"{label} receipt evidence hash mismatch for {path.name}")

    if provisional:
        if validator.get("log_sha256") is not None:
            fail("provisional receipt validator log hash must be null")
        if validator.get("exitcode_file_sha256") is not None:
            fail("provisional receipt validator exit-code hash must be null")
    else:
        validator_evidence = (
            ("log_sha256", validator_log),
            ("exitcode_file_sha256", validator_exit_path),
        )
        for key, path in validator_evidence:
            if validator.get(key) != sha256_file(path):
                fail(f"final receipt evidence hash mismatch for {path.name}")

    counts = parse_collection_log(
        collection_log.read_text(encoding="utf-8", errors="replace")
    )
    for key, value in counts.items():
        if collection.get(key) != value:
            fail(f"{label} receipt collection field {key} does not match log")

    checks = require_exact_keys(
        receipt.get("checks"), set(expected_checks_payload()), f"{label} receipt checks"
    )
    for key, expected in expected_checks_payload().items():
        if checks.get(key) != expected:
            fail(f"{label} receipt checks mismatch for {key}")

    environment = require_exact_keys(
        receipt.get("environment"),
        set(expected_environment_payload()),
        f"{label} receipt environment",
    )
    for key, expected in expected_environment_payload().items():
        if environment.get(key) != expected:
            fail(f"{label} receipt environment mismatch for {key}")

    hash_scope = require_exact_keys(
        receipt.get("hash_scope"),
        set(expected_hash_scope_payload()),
        f"{label} receipt hash_scope",
    )
    for key, expected in expected_hash_scope_payload().items():
        if hash_scope.get(key) != expected:
            fail(f"{label} receipt hash scope mismatch for {key}")

    observed = require_exact_keys(
        receipt.get("observed_file_sha256"),
        set(REQUIRED_READ_PATHS),
        f"{label} receipt observed_file_sha256",
    )
    for rel, expected in expected_observed_file_hashes(args).items():
        if observed.get(rel) != expected:
            fail(f"{label} receipt observed source hash mismatch for {rel}")

    validate_exact_path_array(receipt, "changed_files")
    validate_exact_path_array(receipt, "authorized_changed_paths")

    if not provisional:
        finalizer = require_exact_keys(
            receipt.get("finalizer"), {"command", "exit_code"}, "final receipt finalizer"
        )
        if finalizer.get("command") != expected_finalizer_command(args):
            fail("final receipt finalizer command mismatch")
        if finalizer.get("exit_code") != 0:
            fail("final receipt finalizer exit code mismatch")


def verify_receipt_pair(
    partial: dict[str, Any], final: dict[str, Any], args: argparse.Namespace
) -> None:
    verify_receipt_payload(final, args)
    validate_partial_receipt_payload(partial, final, args)


def validate_partial_receipt_payload(
    partial: dict[str, Any], final: dict[str, Any], args: argparse.Namespace
) -> None:
    validate_receipt_claims(partial, args, provisional=True)

    expected = copy.deepcopy(partial)
    expected_validator = expected["validator"]
    expected_validator["log_sha256"] = sha256_file(Path(args.validator_log).resolve())
    expected_validator["exitcode_file_sha256"] = sha256_file(
        Path(args.validator_exitcode_file).resolve()
    )
    expected["finalizer"] = {
        "command": expected_finalizer_command(args),
        "exit_code": 0,
    }
    expected["evidence_sha256"] = compute_evidence_hash(expected)
    if expected != final:
        fail("provisional-to-final receipt delta mismatch")


def verify_receipt_payload(receipt: dict[str, Any], args: argparse.Namespace) -> None:
    validate_receipt_claims(receipt, args, provisional=False)

def mutate_and_rehash(
    receipt: dict[str, Any], mutation: Callable[[dict[str, Any]], None]
) -> dict[str, Any]:
    mutated = copy.deepcopy(receipt)
    mutation(mutated)
    mutated["evidence_sha256"] = compute_evidence_hash(mutated)
    return mutated


def run_receipt_negative_fixtures(
    receipt: dict[str, Any], args: argparse.Namespace
) -> None:
    identity_mutations: tuple[tuple[str, Any], ...] = (
        ("repository", "example/other"),
        ("pull_request", args.expected_pr_number + 1),
        ("branch", "other-branch"),
        ("base_sha", "0" * 40),
        ("head_sha", "1" * 40),
        ("identity_source", "untrusted-source"),
    )
    for field, value in identity_mutations:
        mutated = mutate_and_rehash(
            receipt, lambda data, f=field, v=value: data.__setitem__(f, v)
        )
        expect_failure(
            lambda data=mutated: verify_receipt_payload(data, args),
            f"receipt identity mutation {field}",
            f"identity mismatch for {field}",
        )

    mutated_command = mutate_and_rehash(
        receipt,
        lambda data: data["validator"].__setitem__(
            "command", ["python", "other-validator.py"]
        ),
    )
    expect_failure(
        lambda: verify_receipt_payload(mutated_command, args),
        "receipt validator command mutation",
        "validator command mismatch",
    )

    reference_mutations = (
        ("collection", "log_file"),
        ("collection", "exitcode_file"),
        ("validator", "log_file"),
        ("validator", "exitcode_file"),
    )
    for section, field in reference_mutations:
        mutated = mutate_and_rehash(
            receipt,
            lambda data, s=section, f=field: data[s].__setitem__(
                f, f"substituted-{f}"
            ),
        )
        expect_failure(
            lambda data=mutated: verify_receipt_payload(data, args),
            f"receipt evidence reference mutation {section}.{field}",
            f"reference mismatch for {field}",
        )

    for field in ("changed_files", "authorized_changed_paths"):
        duplicated = mutate_and_rehash(
            receipt,
            lambda data, f=field: data[f].append(data[f][0]),
        )
        expect_failure(
            lambda data=duplicated: verify_receipt_payload(data, args),
            f"receipt duplicate path entry {field}",
            f"{field} contains duplicate entries",
        )



def run_partial_receipt_negative_fixtures(
    partial: dict[str, Any], final: dict[str, Any], args: argparse.Namespace
) -> None:
    tampered = copy.deepcopy(partial)
    tampered["result"] = "FAIL"
    expect_failure(
        lambda: validate_partial_receipt_payload(tampered, final, args),
        "tampered provisional receipt hash",
        "partial receipt evidence SHA-256 mismatch",
    )

    direct_cases: tuple[
        tuple[str, Callable[[dict[str, Any]], None], str], ...
    ] = (
        (
            "provisional receipt schema mutation",
            lambda data: data.__setitem__("schema_version", 3),
            "partial receipt is not schema-2 PASS",
        ),
        (
            "provisional receipt result mutation",
            lambda data: data.__setitem__("result", "FAIL"),
            "partial receipt is not schema-2 PASS",
        ),
        (
            "provisional identity mutation",
            lambda data: data.__setitem__("repository", "example/other"),
            "provisional receipt authenticated identity mismatch for repository",
        ),
        (
            "provisional validator command mutation",
            lambda data: data["validator"].__setitem__(
                "command", ["python", "other-validator.py"]
            ),
            "provisional receipt validator command mismatch",
        ),
        (
            "provisional collection mutation",
            lambda data: data["collection"].__setitem__(
                "command", ["bash", "other-safe-suite.sh"]
            ),
            "provisional receipt collection command mismatch",
        ),
        (
            "provisional changed-path mutation",
            lambda data: data["changed_files"].append("unexpected/path.txt"),
            "changed_files does not equal exact sorted authorized paths",
        ),
        (
            "provisional finalizer insertion",
            lambda data: data.__setitem__(
                "finalizer", {"command": ["false"], "exit_code": 1}
            ),
            "provisional receipt must not contain finalizer",
        ),
        (
            "provisional validator log hash populated early",
            lambda data: data["validator"].__setitem__("log_sha256", "0" * 64),
            "provisional receipt validator log hash must be null",
        ),
        (
            "provisional validator exit hash populated early",
            lambda data: data["validator"].__setitem__(
                "exitcode_file_sha256", "0" * 64
            ),
            "provisional receipt validator exit-code hash must be null",
        ),
        (
            "provisional validator log reference substitution",
            lambda data: data["validator"].__setitem__(
                "log_file", "substituted-validator.log"
            ),
            "provisional receipt evidence-file reference mismatch for validator.log_file",
        ),
        (
            "provisional validator exit reference substitution",
            lambda data: data["validator"].__setitem__(
                "exitcode_file", "substituted-validator.exitcode"
            ),
            "provisional receipt evidence-file reference mismatch for validator.exitcode_file",
        ),
        (
            "provisional unknown field insertion",
            lambda data: data.__setitem__("unauthenticated_claim", "value"),
            "provisional receipt top-level fields keys mismatch",
        ),
    )
    for label, mutation, diagnostic in direct_cases:
        mutated = mutate_and_rehash(partial, mutation)
        expect_failure(
            lambda data=mutated: validate_partial_receipt_payload(data, final, args),
            label,
            diagnostic,
        )

    paired_cases: tuple[
        tuple[str, Callable[[dict[str, Any]], None], str], ...
    ] = (
        (
            "paired checks claim mutation",
            lambda data: data["checks"].__setitem__("authority_statuses", "FAIL"),
            "final receipt checks mismatch for authority_statuses",
        ),
        (
            "paired environment claim mutation",
            lambda data: data["environment"].__setitem__(
                "platform", "substituted-platform"
            ),
            "final receipt environment mismatch for platform",
        ),
        (
            "paired observed source hash mutation",
            lambda data: data["observed_file_sha256"].__setitem__(
                "AGENTS.md", "0" * 64
            ),
            "final receipt observed source hash mismatch for AGENTS.md",
        ),
        (
            "paired hash-scope claim mutation",
            lambda data: data["hash_scope"].__setitem__(
                "repository_sources", "substituted-scope"
            ),
            "final receipt hash scope mismatch for repository_sources",
        ),
        (
            "paired unknown field insertion",
            lambda data: data.__setitem__("unauthenticated_claim", "value"),
            "final receipt top-level fields keys mismatch",
        ),
    )
    for label, mutation, diagnostic in paired_cases:
        mutated_partial = mutate_and_rehash(partial, mutation)
        mutated_final = mutate_and_rehash(final, mutation)
        expect_failure(
            lambda p=mutated_partial, f=mutated_final: verify_receipt_pair(p, f, args),
            label,
            diagnostic,
        )

def read_json_receipt(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing {label} receipt file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid {label} receipt JSON: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} receipt must be a JSON object")
    return payload



def run_partial_receipt_file_negative_fixtures(
    final: dict[str, Any], args: argparse.Namespace
) -> None:
    with tempfile.TemporaryDirectory(prefix="pr319-partial-receipt-") as tmp:
        temp = Path(tmp)
        missing = temp / "missing.json"
        expect_failure(
            lambda: read_json_receipt(missing, "provisional"),
            "missing provisional receipt file",
            "missing provisional receipt file",
        )

        malformed = temp / "malformed.json"
        malformed.write_text("{not-json", encoding="utf-8")
        expect_failure(
            lambda: read_json_receipt(malformed, "provisional"),
            "malformed provisional receipt file",
            "invalid provisional receipt JSON",
        )

        non_object = temp / "non-object.json"
        non_object.write_text("[]", encoding="utf-8")
        expect_failure(
            lambda: read_json_receipt(non_object, "provisional"),
            "non-object provisional receipt file",
            "provisional receipt must be a JSON object",
        )

        substituted = temp / "substituted.json"
        substituted.write_text(json.dumps(final), encoding="utf-8")
        substituted_payload = read_json_receipt(substituted, "provisional")
        expect_failure(
            lambda: validate_partial_receipt_payload(
                substituted_payload, final, args
            ),
            "substituted provisional receipt file",
            "provisional receipt must not contain finalizer",
        )

def verify_receipt(args: argparse.Namespace) -> None:
    receipt_path = Path(args.receipt).resolve()
    partial_path = Path(args.partial_receipt).resolve()
    receipt = read_json_receipt(receipt_path, "final")
    partial = read_json_receipt(partial_path, "provisional")
    verify_receipt_payload(receipt, args)
    validate_partial_receipt_payload(partial, receipt, args)
    run_receipt_negative_fixtures(receipt, args)
    run_partial_receipt_negative_fixtures(partial, receipt, args)
    run_partial_receipt_file_negative_fixtures(receipt, args)

def write_json(path: str | None, payload: dict[str, Any]) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path:
        Path(path).write_text(rendered, encoding="utf-8")
    print(rendered, end="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)

    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("--repo-root", default=".")
    validate_parser.add_argument("--github-head-sha", required=True)
    validate_parser.add_argument("--github-base-sha", required=True)
    validate_parser.add_argument("--pr-number", required=True, type=int)
    validate_parser.add_argument("--branch-name", required=True)
    validate_parser.add_argument("--identity-source", default="authenticated-github")
    validate_parser.add_argument("--collection-log", required=True)
    validate_parser.add_argument("--collection-exitcode-file", required=True)
    validate_parser.add_argument(
        "--validator-log-name", default="pr319-governance-validator.log"
    )
    validate_parser.add_argument(
        "--validator-exitcode-name", default="pr319-governance-validator.exitcode"
    )
    validate_parser.add_argument("--output", required=True)

    finalize_parser = sub.add_parser("finalize-receipt")
    finalize_parser.add_argument("--input", required=True)
    finalize_parser.add_argument("--output", required=True)
    finalize_parser.add_argument("--validator-log", required=True)
    finalize_parser.add_argument("--validator-exitcode-file", required=True)

    verify_parser = sub.add_parser("verify-receipt")
    verify_parser.add_argument("--receipt", required=True)
    verify_parser.add_argument("--partial-receipt", required=True)
    verify_parser.add_argument("--collection-log", required=True)
    verify_parser.add_argument("--collection-exitcode-file", required=True)
    verify_parser.add_argument("--validator-log", required=True)
    verify_parser.add_argument("--validator-exitcode-file", required=True)
    verify_parser.add_argument("--expected-repository", required=True)
    verify_parser.add_argument("--expected-pr-number", required=True, type=int)
    verify_parser.add_argument("--expected-branch", required=True)
    verify_parser.add_argument("--expected-base-sha", required=True)
    verify_parser.add_argument("--expected-head-sha", required=True)
    verify_parser.add_argument("--expected-identity-source", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.mode == "validate":
            write_json(args.output, validate_repository(args))
        elif args.mode == "finalize-receipt":
            write_json(args.output, finalize_receipt(args))
        elif args.mode == "verify-receipt":
            verify_receipt(args)
            print(json.dumps({"result": "PASS", "receipt": args.receipt}, indent=2))
        else:
            fail(f"unsupported mode: {args.mode}")
    except Exception as exc:
        print(
            json.dumps(
                {
                    "result": "FAIL",
                    "command": [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        *sys.argv[1:],
                    ],
                    "exit_code": 1,
                    "error": str(exc),
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
