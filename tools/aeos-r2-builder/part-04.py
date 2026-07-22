es: list[tuple[str, Any, Path, str, bool]] = []
    x=copy.deepcopy(state); x["schema_version"]=1; cases.append(("new canonical v1 state",x,SCHEMA_ROOT/"state.schema.json","state",False))
    x=copy.deepcopy(state); x["repository"]["head_sha"]=None; cases.append(("null state head",x,SCHEMA_ROOT/"state.schema.json","state",False))
    x=copy.deepcopy(state); x["unexpected"]=True; cases.append(("unknown state field",x,SCHEMA_ROOT/"state.schema.json","state",False))
    x=copy.deepcopy(state); x["lifecycle"]["merge_status"]="INVALID"; cases.append(("invalid lifecycle",x,SCHEMA_ROOT/"state.schema.json","state",False))
    x=copy.deepcopy(state); x["review"]["reviewed_head_sha"]='f'*40; cases.append(("stale reviewed head",x,SCHEMA_ROOT/"state.schema.json","state",True))
    x=copy.deepcopy(state); x["status"]="IN_PROGRESS"; x["authorization"]["authorization_id"]="AUTH"; x["authorization"]["authorized_action"]="work"; x["authorization"]["authorized_state"]="GOVERNANCE_INITIALIZATION"; x["authorization"]["authorized_identity"]={'branch':x['repository']['branch'],'base_sha':x['repository']['base_sha'],'head_sha':'f'*40,'worktree_mode':'remote_only','worktree_id':None,'worktree_path':None,'pull_request':123}; cases.append(("authorization head mismatch",x,SCHEMA_ROOT/"state.schema.json","state",True))
    x=copy.deepcopy(ev); x["evidence"][0]["sha256"]=None; cases.append(("missing byte hash",x,SCHEMA_ROOT/"evidence-index.schema.json","evidence",False))
    x=copy.deepcopy(ev); x["evidence"][0]["hash_scope"]="not_applicable"; cases.append(("not applicable with hash",x,SCHEMA_ROOT/"evidence-index.schema.json","evidence",False))
    x=copy.deepcopy(ev); x["evidence"][0]["repository_head"]='f'*40; cases.append(("evidence head mismatch",x,SCHEMA_ROOT/"evidence-index.schema.json","evidence",True))
    x=copy.deepcopy(cp); x["unexpected"]=True; cases.append(("unknown checkpoint field",x,SCHEMA_ROOT/"checkpoint-request.schema.json","checkpoint",False))
    for label, instance, schema_path, kind, semantic_only in cases:
        failure = assert_rejected(label, instance, schema_path, kind, semantic_only=semantic_only)
        if failure: errors.append(failure)

    errors.extend(validate_legacy_boundary())

    if errors:
        print("AEOS goal-loop contract validation: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    if not args.quiet:
        print("AEOS goal-loop contract validation: PASS")
        print(f"- canonical schemas: {len(MAPPINGS)}")
        print(f"- canonical templates: {len(MAPPINGS)}")
        print(f"- mutation-negative cases: {len(cases)}")
        print("- legacy v1 boundary: enforced")
        print("- root/shared parity: enforced")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
'''
val_path = OUT / '.ai/aeos/bin/validate_goal_loop_contracts.py'
val_path.write_text(validator, encoding='utf-8')
val_path.chmod(0o755)

# Enhanced checksum generator.
generator = r'''#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "CHECKSUMS.txt"


def is_macos_metadata(path: Path) -> bool:
    return path.name == ".DS_Store" or path.name.startswith("._") or "__MACOSX" in path.parts


def expected_lines() -> list[str]:
    metadata = [p for p in ROOT.rglob("*") if is_macos_metadata(p)]
    if metadata:
        raise RuntimeError("macOS metadata present: " + ", ".join(str(p.relative_to(ROOT)) for p in metadata))
    lines=[]
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path == OUTPUT or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(ROOT).as_posix()}")
    return lines


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args=parser.parse_args()
    try:
        text="\n".join(expected_lines())+"\n"
    except RuntimeError as exc:
        print(f"Checksum generation refused: {exc}")
        return 1
    if args.check:
        if not OUTPUT.is_file():
            print("CHECKSUMS.txt missing")
            return 1
        if OUTPUT.read_text(encoding="utf-8") != text:
            print("CHECKSUMS.txt is stale")
            return 1
        print(f"CHECKSUMS.txt current with {len(text.splitlines())} entries")
        return 0
    OUTPUT.write_text(text, encoding="utf-8")
    print(f"Wrote {OUTPUT} with {len(text.splitlines())} entries")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
'''
(OUT / '.ai/aeos/bin/generate_checksums.py').write_text(generator, encoding='utf-8')
(OUT / '.ai/aeos/bin/generate_checksums.py').chmod(0o755)

# Build layout validator from PR320 and add semantic enforcement / strict manifest expectations.
layout = (PR320 / '.ai/aeos/bin/validate_ai_layout.py').read_text(encoding='utf-8')
layout = layout.replace('import json\n', 'import json\nimport subprocess\nimport sys\n')
layout = layout.replace('manifest.get("skills_version") != "1.1.0"', 'manifest.get("skills_version") != "1.2.0"')
layout = layout.replace('skills_version must be 1.1.0', 'skills_version must be 1.2.0')
# Replace pair list with dynamically expanded strict list.
start = layout.index('PAIRED_RESOURCES = [')
end = layout.index(']\nREQUIRED_POINTERS', start) + 2
pair_names = list(templates) + list(schema_map)
pairs = 'PAIRED_RESOURCES = [\n' + ''.join(f'    ("templates/goal-loop/{n}", "agent-skills/_aeos-shared/templates/{n}"),\n' for n in templates) + ''.join(f'    ("schemas/goal-loop/{n}", "agent-skills/_aeos-shared/schemas/{n}"),\n' for n in schema_map) + ''.join(f'    ("schemas/goal-loop/legacy-v1/{n}", "agent-skills/_aeos-shared/schemas/legacy-v1/{n}"),\n' for n in legacy_names + ['README.md']) + ']\n'
layout = layout[:start] + pairs + layout[end:]
# Add required semantic script and permanent workflow.
layout = layout.replace('REPO_ROOT / "docs" / "governance" / "branch-worktree-lifecycle-policy.md",', 'REPO_ROOT / "docs" / "governance" / "branch-worktree-lifecycle-policy.md",\n        ROOT / "aeos" / "bin" / "validate_goal_loop_contracts.py",\n        REPO_ROOT / ".github" / "workflows" / "aeos-governance-validation.yml",')
# Add strict rules.
layout = layout.replace('"representation_scoped_hashes_required",', '"representation_scoped_hashes_required",\n                "canonical_goal_loop_schema_version_2_only",\n                "legacy_v1_requires_registry",\n                "semantic_schema_and_yaml_validation_required",')
# Invoke semantic validator before checksum section.
needle = '    actual, checksum_errors = parse_checksums(ROOT / "CHECKSUMS.txt")\n'
insert = '''    semantic = subprocess.run([sys.executable, str(ROOT / "aeos" / "bin" / "validate_goal_loop_contracts.py"), "--quiet"], capture_output=True, text=True)\n    if semantic.returncode != 0:\n        errors.append("goal-loop semantic validation failed")\n        for line in (semantic.stdout + semantic.stderr).splitlines():\n            if line.strip():\n                errors.append(f"goal-loop: {line}")\n\n'''
layout = layout.replace(needle, insert + needle)
(OUT / '.ai/aeos/bin/validate_ai_layout.py').write_text(layout, encoding='utf-8')
(OUT / '.ai/aeos/bin/validate_ai_layout.py').chmod(0o755)

# Enhance skill validator to invoke semantic validation.
skill_val = (PR320 / '.ai/agent-skills/_aeos-shared/scripts/validate_skill_package.py').read_text(encoding='utf-8')
skill_val = skill_val.replace('import sys\n', 'import sys\nimport subprocess\n')
semantic_insertion = '''\n    semantic_script = skills_root.parent / "aeos" / "bin" / "validate_goal_loop_contracts.py"\n    semantic = subprocess.run([sys.executable, str(semantic_script), "--quiet"], capture_output=True, text=True)\n    if semantic.returncode != 0:\n        errors.append("goal-loop semantic validation failed")\n        for line in (semantic.stdout + semantic.stderr).splitlines():\n            if line.strip():\n                errors.append(f"goal-loop: {line}")\n'''
skill_val = skill_val.replace('    package_root = skills_root\n', semantic_insertion + '\n    package_root = skills_root\n')
(OUT / '.ai/agent-skills/_aeos-shared/scripts/validate_skill_package.py').write_text(skill_val, encoding='utf-8')
(OUT / '.ai/agent-skills/_aeos-shared/scripts/validate_skill_package.py').chmod(0o755)

# Manifest v1.2.
manifest = json.loads((PR320 / '.ai/AGENT-SKILLS-MANIFEST.json').read_text(encoding='utf-8'))
manifest['schema_version'] = 2
manifest['skills_version'] = '1.2.0'
manifest.setdefault('rules', {}).update({
    'canonical_goal_loop_schema_version_2_only': True,
    'legacy_v1_requires_registry': True,
    'semantic_schema_and_yaml_validation_required': True,
})
(OUT / '.ai/AGENT-SKILLS-MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')

# Dev dependency for standards-compliant JSON Schema validation.
pyproject = OUT / 'pyproject.toml'
text = pyproject.read_text(encoding='utf-8')
if '"jsonschema>=' not in text:
    text = text.replace('  "types-PyYAML>=6.0",', '  "types-PyYAML>=6.0",\n  "jsonschema>=4.23",')
pyproject.write_text(text, encoding='utf-8')

# Permanent PR validation workflow.
workflow = '''name: AEOS Governance Validation\n\non:\n  pull_request:\n    paths:\n      - "AI_OPERATING_MANUAL.md"\n      - ".ai/**"\n      - "pyproject.toml"\n      - ".github/workflows/aeos-governance-validation.yml"\n  push:\n    branches: [main]\n    paths:\n      - "AI_OPERATING_MANUAL.md"\n      - ".ai/**"\n      - "pyproject.toml"\n      - ".github/workflows/aeos-governance-validation.yml"\n\npermissions:\n  contents: read\n\njobs:\n  validate:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-python@v5\n        with:\n          python-version: "3.12"\n      - name: Install governance validation dependencies\n        run: python -m pip install --disable-pip-version-check -e ".[dev]"\n      - name: Compile validator sources\n        run: python -m compileall -q .ai/aeos/bin .ai/agent-skills/_aeos-shared/scripts\n      - name: Validate goal-loop contracts\n        run: python .ai/aeos/bin/validate_goal_loop_contracts.py\n      - name: Validate AEOS skill package\n        run: python .ai/agent-skills/_aeos-shared/scripts/validate_skill_package.py\n      - name: Validate AI layout and checksums\n        run: python .ai/aeos/bin/validate_ai_layout.py\n      - name: Verify checksum manifest without mutation\n        run: python .ai/aeos/bin/generate_checksums.py --check\n'''
wf = OUT / '.github/workflows/aeos-governance-validation.yml'
wf.parent.mkdir(parents=True, exist_ok=True)
wf.write_text(workflow, encoding='utf-8')

# Remove obsolete schemas.
for name in ['aeos_artifact_metadata.schema.json','aeos_finding.schema.json','aeos_go_no_go.schema.json']:
    (OUT / '.ai/schemas/aeos-core' / name).unlink(missing_ok=True)

# Update branch receipt with PR identity, preserving non-self-referential roles.
receipt_path = OUT / 'docs/evidence/aeos-governance-sync-r2/branch-registration.yaml'
receipt = receipt_path.read_text(encoding='utf-8')
receipt = receipt.replace('pull_request: null', 'pull_request: 323')
receipt_path.write_text(receipt, encoding='utf-8')

# Regenerate convenience bundle from current source generation.
bundle = OUT / '.ai/reference-bundles/AEOS_Governance_Combined_Manual_v1.2.md'
parts = ['# AEOS Governance Documents v1.2\n\nThis non-canonical convenience bundle is generated from the individual governing source files. The source files remain authoritative.\n']
for i in range(12):
    matches = sorted((OUT / '.ai/project-sources').glob(f'{i:02d}_*.md'))
    for path in matches:
        parts.append('\n\n---\n\n' + path.read_text(encoding='utf-8'))
bundle.write_text(''.join(parts).rstrip()+'\n', encoding='utf-8')

# Keep v1.1 bundle historical if present; no overwrite.

# Regenerate checksums after all final .ai content.
import subprocess, sys
subprocess.run([sys.executable, str(OUT / '.ai/aeos/bin/generate_checksums.py')], cwd=OUT, check=True)

print('Built corrective tree:', OUT)
