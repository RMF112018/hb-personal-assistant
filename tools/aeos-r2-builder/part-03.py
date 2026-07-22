f yaml_dump(data, indent=0):
    # PyYAML is a project dependency; import here only for generation.
    import yaml
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)

templates = {
    'state.template.yaml':yaml_dump(state),
    'checkpoint-request.template.yaml':yaml_dump(checkpoint),
    'evidence-index.template.json':json.dumps(evidence, indent=2)+'\n',
    'authorization.template.yaml':yaml_dump(authorization),
    'external-review.template.yaml':yaml_dump(external_review),
    'finding-ledger.template.yaml':yaml_dump(finding),
    'governance-manifest.template.yaml':yaml_dump(gov),
    'work-item-ledger.template.yaml':yaml_dump(work),
}
for name, content in templates.items():
    for base in [OUT / '.ai/templates/goal-loop', OUT / '.ai/agent-skills/_aeos-shared/templates']:
        base.mkdir(parents=True, exist_ok=True)
        (base / name).write_text(content, encoding='utf-8')

# Positive fixtures are exact copies of canonical templates.
fixture_dir = OUT / '.ai/tests/goal-loop/fixtures'
fixture_dir.mkdir(parents=True, exist_ok=True)
for src_name, fixture_name in [
    ('state.template.yaml','state.valid.yaml'),('checkpoint-request.template.yaml','checkpoint.valid.yaml'),
    ('evidence-index.template.json','evidence.valid.json'),('authorization.template.yaml','authorization.valid.yaml'),
    ('external-review.template.yaml','external-review.valid.yaml'),('finding-ledger.template.yaml','finding-ledger.valid.yaml'),
    ('governance-manifest.template.yaml','governance-manifest.valid.yaml'),('work-item-ledger.template.yaml','work-item-ledger.valid.yaml')]:
    shutil.copy2(OUT / '.ai/templates/goal-loop' / src_name, fixture_dir / fixture_name)

# Semantic validator.
validator = r'''#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit("PyYAML is required; install the project dependencies") from exc
try:
    from jsonschema import Draft202012Validator, FormatChecker
    from jsonschema.exceptions import SchemaError, ValidationError
except ImportError as exc:
    raise SystemExit("jsonschema is required; install the dev extra: pip install -e '.[dev]'") from exc

AI_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = AI_ROOT.parent
SCHEMA_ROOT = AI_ROOT / "schemas" / "goal-loop"
SHARED_ROOT = AI_ROOT / "agent-skills" / "_aeos-shared"
TEMPLATE_ROOT = AI_ROOT / "templates" / "goal-loop"
FIXTURE_ROOT = AI_ROOT / "tests" / "goal-loop" / "fixtures"
LEGACY_ROOT = AI_ROOT / "aeos" / "legacy-v1"
HEX40 = set("0123456789abcdef")

MAPPINGS = {
    "state.template.yaml": "state.schema.json",
    "checkpoint-request.template.yaml": "checkpoint-request.schema.json",
    "evidence-index.template.json": "evidence-index.schema.json",
    "authorization.template.yaml": "authorization.schema.json",
    "external-review.template.yaml": "external-review.schema.json",
    "finding-ledger.template.yaml": "finding-ledger.schema.json",
    "governance-manifest.template.yaml": "governance-manifest.schema.json",
    "work-item-ledger.template.yaml": "work-item-ledger.schema.json",
}
PAIR_RELS = [
    *((f"templates/goal-loop/{name}", f"templates/{name}") for name in MAPPINGS),
    *((f"schemas/goal-loop/{name}", f"schemas/{name}") for name in sorted(set(MAPPINGS.values()))),
    *((f"schemas/goal-loop/legacy-v1/{name}", f"schemas/legacy-v1/{name}") for name in ["state.schema.json","checkpoint-request.schema.json","evidence-index.schema.json","README.md"]),
]


def load_data(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def schema_validator(schema_path: Path) -> Draft202012Validator:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_instance(instance: Any, schema_path: Path) -> list[str]:
    validator = schema_validator(schema_path)
    return [error.message for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.path))]


def semantic_errors(kind: str, data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    repo = data.get("repository", {})
    head = repo.get("head_sha") or repo.get("reviewed_head_sha")
    if kind == "state":
        review = data["review"]
        auth = data["authorization"]
        state = data["state"]
        lifecycle = data["lifecycle"]
        if review["reviewed_head_sha"] is not None and review["reviewed_head_sha"] != repo["head_sha"]:
            errors.append("reviewed_head_sha must equal repository.head_sha")
        identity = auth["authorized_identity"]
        if identity is not None:
            for key in ["branch","base_sha","head_sha","worktree_mode","worktree_id","worktree_path","pull_request"]:
                expected = repo[key]
                actual = identity[key]
                if actual != expected:
                    errors.append(f"authorization identity mismatch for {key}")
        if data["status"] not in {"NOT_STARTED","BLOCKED"} and auth["required"]:
            if not auth["authorization_id"] or not auth["authorized_action"] or identity is None:
                errors.append("active state requires complete authorization identity")
        if state == "MERGED_PENDING_CLEANUP" and lifecycle["merge_status"] != "MERGED_PENDING_CLEANUP":
            errors.append("MERGED_PENDING_CLEANUP state requires matching merge_status")
        if state == "POST_MERGE_VALIDATION" and lifecycle["post_merge_validation"] not in {"PENDING","COMPLETE","NOT_REQUIRED","BLOCKED"}:
            errors.append("POST_MERGE_VALIDATION state has inconsistent lifecycle")
        if state == "CLOSED":
            if lifecycle["merge_status"] != "MERGED" or lifecycle["post_merge_validation"] not in {"COMPLETE","NOT_REQUIRED"} or lifecycle["cleanup_disposition"] not in {"COMPLETE","RETAINED"} or lifecycle["closure_status"] != "CLOSED":
                errors.append("CLOSED state requires merged, validated, dispositioned lifecycle")
    elif kind == "checkpoint":
        if data["disposition"] == "MERGED_PENDING_CLEANUP" and data["current_state"] != "MERGED_PENDING_CLEANUP":
            errors.append("MERGED_PENDING_CLEANUP disposition requires matching current_state")
        if data["current_state"] == "CLOSED" and data["lifecycle"]["closure_status"] != "CLOSED":
            errors.append("closed checkpoint requires closed lifecycle")
    elif kind == "evidence":
        for item in data["evidence"]:
            if item["repository_head"] != repo["head_sha"]:
                errors.append(f"{item['evidence_id']}: repository_head mismatch")
            if item["hash_scope"] == "not_applicable" and item["sha256"] is not None:
                errors.append(f"{item['evidence_id']}: not_applicable must not carry sha256")
            if item["hash_scope"] != "not_applicable" and item["sha256"] is None:
                errors.append(f"{item['evidence_id']}: byte-bearing hash scope requires sha256")
    elif kind == "external-review":
        if not data["stale_on_head_change"]:
            errors.append("review must stale on head change")
    elif kind == "authorization":
        if data["repository"]["head_sha"] != data["repository"]["head_sha"]:
            errors.append("unreachable identity mismatch")
    return errors


def assert_rejected(label: str, instance: Any, schema_path: Path, kind: str, *, semantic_only: bool = False) -> str | None:
    schema_errors = validate_instance(instance, schema_path)
    sem_errors = semantic_errors(kind, instance) if not schema_errors else []
    if semantic_only:
        if sem_errors:
            return None
        return f"negative mutation unexpectedly passed semantic validation: {label}"
    if schema_errors or sem_errors:
        return None
    return f"negative mutation unexpectedly validated: {label}"


def validate_legacy_boundary() -> list[str]:
    errors: list[str] = []
    registry_path = LEGACY_ROOT / "registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    allowed = {item["path"]: item["sha256"] for item in registry.get("allowed_records", [])}
    for rel, digest in allowed.items():
        path = REPO_ROOT / rel
        if not path.is_file():
            errors.append(f"legacy registry path missing: {rel}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != digest:
            errors.append(f"legacy registry hash mismatch: {rel}")
    goals = AI_ROOT / "aeos" / "goals"
    if goals.exists():
        for path in goals.rglob("*"):
            if not path.is_file() or path.suffix not in {".json",".yaml",".yml"}:
                continue
            try:
                data = load_data(path)
            except Exception:
                continue
            if isinstance(data, dict) and data.get("schema_version") == 1:
                errors.append(f"canonical goal path contains prohibited v1 record: {path.relative_to(REPO_ROOT)}")
    if LEGACY_ROOT.exists():
        for path in LEGACY_ROOT.rglob("*"):
            if not path.is_file() or path.name == "registry.json" or path.suffix not in {".json",".yaml",".yml"}:
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel not in allowed:
                errors.append(f"unregistered legacy v1 record: {rel}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []

    # Meta-schema validation and root/shared parity.
    for schema_path in sorted(SCHEMA_ROOT.rglob("*.json")):
        try:
            schema_validator(schema_path)
        except (SchemaError, json.JSONDecodeError) as exc:
            errors.append(f"invalid JSON Schema {schema_path.relative_to(REPO_ROOT)}: {exc}")
    for root_rel, shared_rel in PAIR_RELS:
        root_path = AI_ROOT / root_rel
        shared_path = SHARED_ROOT / shared_rel
        if not root_path.is_file() or not shared_path.is_file():
            errors.append(f"missing paired contract: {root_rel} <-> {shared_rel}")
        elif root_path.read_bytes() != shared_path.read_bytes():
            errors.append(f"root/shared contract diverged: {root_rel} <-> {shared_rel}")

    # Parse every structured template in both surfaces.
    for template_root in [TEMPLATE_ROOT, SHARED_ROOT / "templates"]:
        for path in sorted(template_root.glob("*")):
            if path.suffix not in {".yaml",".yml",".json"}:
                continue
            try:
                load_data(path)
            except Exception as exc:
                errors.append(f"invalid structured template {path.relative_to(REPO_ROOT)}: {exc}")

    # Validate canonical templates and fixtures.
    kind_by_template = {
        "state.template.yaml":"state","checkpoint-request.template.yaml":"checkpoint","evidence-index.template.json":"evidence",
        "authorization.template.yaml":"authorization","external-review.template.yaml":"external-review","finding-ledger.template.yaml":"finding",
        "governance-manifest.template.yaml":"governance","work-item-ledger.template.yaml":"work-item",
    }
    for template_name, schema_name in MAPPINGS.items():
        path = TEMPLATE_ROOT / template_name
        instance = load_data(path)
        schema_errors = validate_instance(instance, SCHEMA_ROOT / schema_name)
        for err in schema_errors:
            errors.append(f"{template_name}: {err}")
        for err in semantic_errors(kind_by_template[template_name], instance):
            errors.append(f"{template_name}: {err}")

    fixture_map = {
        "state.valid.yaml":("state.schema.json","state"),"checkpoint.valid.yaml":("checkpoint-request.schema.json","checkpoint"),
        "evidence.valid.json":("evidence-index.schema.json","evidence"),"authorization.valid.yaml":("authorization.schema.json","authorization"),
        "external-review.valid.yaml":("external-review.schema.json","external-review"),"finding-ledger.valid.yaml":("finding-ledger.schema.json","finding"),
        "governance-manifest.valid.yaml":("governance-manifest.schema.json","governance"),"work-item-ledger.valid.yaml":("work-item-ledger.schema.json","work-item"),
    }
    fixtures: dict[str, Any] = {}
    for name, (schema_name, kind) in fixture_map.items():
        data = load_data(FIXTURE_ROOT / name); fixtures[name] = data
        for err in validate_instance(data, SCHEMA_ROOT / schema_name) + semantic_errors(kind, data):
            errors.append(f"fixture {name}: {err}")

    # Mutation-negative matrix.
    state = fixtures["state.valid.yaml"]
    cp = fixtures["checkpoint.valid.yaml"]
    ev = fixtures["evidence.valid.json"]
    cas