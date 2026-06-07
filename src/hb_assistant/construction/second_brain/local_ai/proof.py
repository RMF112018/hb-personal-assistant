"""Phase 10 Prompt 01 — contracts/seeds/fixtures proof (advisory, read-only).

Builds a metadata-only proof that the Phase 10 contracts, seed policies, and synthetic fixtures
load and validate against their Pydantic contracts, and that none of them carry restricted raw
content (secrets, tokens, signed URLs, raw bodies). It performs **no** DB access, **no** Ollama
call, **no** external request, and **no** writeback. The only optional side effect is writing the
evidence JSON/MD when ``write_evidence=True``.

Public entry point:
    build_phase_10_contracts_proof(*, evidence_dir=None, write_evidence=False) -> dict
CLI: hb-assistant second-brain phase-10 contracts-proof --json
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

from .contracts import (
    PHASE_10_CONTRACT_FILES,
    PHASE_10_SEED_FILES,
    Phase10ContractError,
    load_ai_job_policy,
    load_all_phase_10_contracts,
    load_local_model_profiles,
    load_mcp_packet_policy,
    load_obsidian_vault_policy,
)

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-10-local-action-intelligence"
_PROOF_JSON = "01-contracts-seeds-proof.json"
_PROOF_MD = "01-contracts-seeds-proof.md"

# Fixtures bundled with the test suite; the proof validates them structurally (they are
# extraction fixtures, not raw candidate records).
_FIXTURES: tuple[tuple[str, str], ...] = (
    ("email_task_candidate_001", "tests/fixtures/local_ai/email_task_candidate_001.json"),
    ("commitment_candidate_001", "tests/fixtures/local_ai/commitment_candidate_001.json"),
    ("follow_up_monitor_001", "tests/fixtures/local_ai/follow_up_monitor_001.json"),
    ("relationship_candidate_001", "tests/fixtures/local_ai/relationship_candidate_001.json"),
    ("daily_brief_packet_001", "tests/fixtures/mcp/daily_brief_packet_001.json"),
)

# Secret/token/signed-URL detectors (labels only ever surface, never the matched value).
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("pem_private_key", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    ("bearer_token", re.compile(r"Bearer [A-Za-z0-9._-]{20,}")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}")),
    ("sas_signed_param", re.compile(r"[?&](sig|sv|se|token)=[A-Za-z0-9%._-]{16,}")),
    ("signed_url", re.compile(r"https?://[^\s\"']*[?&](sig|token)=")),
    ("oauth_secret", re.compile(r"access_token|refresh_token|client_secret")),
]

# Raw-payload key names that must never appear with content in any artifact.
_FORBIDDEN_RAW_KEYS: frozenset[str] = frozenset(
    {
        "raw_email_body",
        "raw_document_text",
        "raw_calendar_payload",
        "raw_procore_payload",
        "raw_prompt",
        "raw_response",
        "signed_url",
        "download_url",
        "token",
        "secret",
    }
)


class Phase10ProofError(RuntimeError):
    """Raised when the Phase 10 contracts proof cannot be assembled (fail-closed)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_root() -> Path:
    return PathPolicy().resolve_repo_root()


def _repo_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=_repo_root(), stderr=subprocess.DEVNULL, timeout=5
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def _scan_forbidden(label: str, payload: Any, text: str) -> list[dict[str, str]]:
    """Return forbidden-content findings (artifact label + finding kind only; never the value)."""
    findings: list[dict[str, str]] = []
    for kind, pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            findings.append({"artifact": label, "finding": kind})

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in _FORBIDDEN_RAW_KEYS:
                    findings.append({"artifact": label, "finding": f"forbidden_key:{key}"})
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(payload)
    return findings


def _validate_fixture(fixture_id: str, data: dict[str, Any], contracts: dict[str, Any]) -> None:
    """Structurally validate a fixture against the relevant contract enums (raises on failure)."""
    action_enums = contracts["action_candidate_output_schema"]["properties"]
    if fixture_id in ("email_task_candidate_001", "commitment_candidate_001"):
        if not data.get("source_ref"):
            raise Phase10ProofError(f"{fixture_id}: missing source_ref")
        exp = data.get("expected", {})
        _require_enum(fixture_id, "candidate_type", exp.get("candidate_type"), action_enums)
        _require_enum(fixture_id, "assignee", exp.get("assignee"), action_enums)
        _require_enum(fixture_id, "waiting_state", exp.get("waiting_state"), action_enums)
        _require_enum(
            fixture_id, "recommended_next_action", exp.get("recommended_next_action"), action_enums
        )
    elif fixture_id == "follow_up_monitor_001":
        statuses = contracts["follow_up_watch_contract"]["statuses"]
        if data.get("expected_watch_status") not in statuses:
            raise Phase10ProofError(f"{fixture_id}: expected_watch_status not in contract")
    elif fixture_id == "relationship_candidate_001":
        rel_types = contracts["relationship_candidate_contract"]["relationship_types"]
        if data.get("expected_relationship_type") not in rel_types:
            raise Phase10ProofError(f"{fixture_id}: expected_relationship_type not in contract")
        if not data.get("email_thread", {}).get("source_ref"):
            raise Phase10ProofError(f"{fixture_id}: missing email source_ref")
    elif fixture_id == "daily_brief_packet_001":
        packet = contracts["claude_mcp_packet_contract"]
        if data.get("packet_type") not in packet["packet_types"]:
            raise Phase10ProofError(f"{fixture_id}: packet_type not in contract")
        required = set(packet["required_item_fields"])
        for item in data.get("items", []):
            missing = required - set(item)
            if missing:
                raise Phase10ProofError(f"{fixture_id}: item missing {sorted(missing)}")
        if data.get("expected", {}).get("source_ref_count") != len(data.get("items", [])):
            raise Phase10ProofError(f"{fixture_id}: source_ref_count mismatch")


def _require_enum(fixture_id: str, field: str, value: Any, action_enums: dict[str, Any]) -> None:
    allowed = action_enums.get(field, {}).get("enum")
    if allowed is not None and value not in allowed:
        raise Phase10ProofError(f"{fixture_id}: {field}={value!r} not in contract enum")


def build_phase_10_contracts_proof(
    *,
    evidence_dir: str | None = None,
    write_evidence: bool = False,
) -> dict[str, Any]:
    """Validate Phase 10 contracts + seeds + fixtures and return a metadata-only proof envelope."""
    errors: list[str] = []
    forbidden_findings: list[dict[str, str]] = []

    # 1. Contracts load (fail-closed) + provenance assertion on the candidate schema.
    contracts: dict[str, Any] = {}
    contracts_loaded = False
    try:
        contracts = load_all_phase_10_contracts()
        contracts_loaded = len(contracts) == len(PHASE_10_CONTRACT_FILES)
    except (Phase10ContractError, KeyError) as exc:
        errors.append(f"contracts_load: {exc}")

    provenance_required = False
    if contracts_loaded:
        schema = contracts["action_candidate_output_schema"]
        required = set(schema.get("required", []))
        source_refs = schema.get("properties", {}).get("source_refs", {})
        provenance_required = (
            {"source_refs", "confidence"} <= required and source_refs.get("minItems") == 1
        )
        if not provenance_required:
            errors.append("provenance_required: candidate schema must require source_refs/confidence")
        for name, body in contracts.items():
            forbidden_findings.extend(_scan_forbidden(f"contract:{name}", body, json.dumps(body)))

    # 2. Seeds load + Pydantic validation (fail-closed).
    seed_versions: dict[str, str] = {}
    seeds_valid = False
    try:
        loaders: dict[str, Callable[[], BaseModel]] = {
            "local_model_profiles": load_local_model_profiles,
            "ai_job_policy": load_ai_job_policy,
            "obsidian_vault_policy": load_obsidian_vault_policy,
            "mcp_packet_policy": load_mcp_packet_policy,
        }
        for name, loader in loaders.items():
            model = loader()
            seed_versions[name] = model.version
            dumped = model.model_dump()
            forbidden_findings.extend(_scan_forbidden(f"seed:{name}", dumped, json.dumps(dumped)))
        seeds_valid = len(seed_versions) == len(PHASE_10_SEED_FILES)
    except (Phase10ContractError, ValidationError, KeyError) as exc:
        errors.append(f"seeds_valid: {exc}")

    # 3. Fixtures: parse + structural validation + forbidden-content scan.
    fixtures_validated: list[str] = []
    fixtures_valid = False
    if contracts_loaded:
        try:
            root = _repo_root()
            for fixture_id, rel in _FIXTURES:
                path = root / rel
                if not path.exists():
                    raise Phase10ProofError(f"fixture {fixture_id} not found at {rel}")
                data = json.loads(path.read_text(encoding="utf-8"))
                _validate_fixture(fixture_id, data, contracts)
                forbidden_findings.extend(
                    _scan_forbidden(f"fixture:{fixture_id}", data, path.read_text(encoding="utf-8"))
                )
                fixtures_validated.append(fixture_id)
            fixtures_valid = len(fixtures_validated) == len(_FIXTURES)
        except (Phase10ProofError, ValueError) as exc:
            errors.append(f"fixtures_valid: {exc}")

    no_forbidden_content = len(forbidden_findings) == 0

    gates = {
        "contracts_load": contracts_loaded,
        "seeds_valid": seeds_valid,
        "fixtures_valid": fixtures_valid,
        "provenance_required": provenance_required,
        "no_forbidden_content": no_forbidden_content,
    }
    proof_passed = all(gates.values())

    result: dict[str, Any] = {
        "proof": "phase_10_contracts_proof",
        "command": "second-brain phase-10 contracts-proof",
        "phase": "10",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "schema_version": LATEST_SCHEMA_VERSION,
        "proof_passed": proof_passed,
        "overall_status": "clean" if proof_passed else "findings",
        "gates": gates,
        "contract_count": len(contracts),
        "contracts": sorted(PHASE_10_CONTRACT_FILES),
        "seed_count": len(seed_versions),
        "seed_versions": seed_versions,
        "fixtures_validated": fixtures_validated,
        "forbidden_findings": forbidden_findings,
        "errors": errors,
        "guard_attestation": {
            "advisory_only": True,
            "read_only": True,
            "metadata_only": True,
            "makes_determination": False,
            "no_external_writeback": True,
            "no_raw_persistence": True,
            "no_ollama_call": True,
            "no_db_access": True,
        },
        "guardrails": {
            "local_first": True,
            "structured_output_validated": True,
            "high_stakes_review_only": True,
            "candidate_requires_source_refs": True,
            "environment_isolation_intended": True,
        },
    }

    if write_evidence:
        result["evidence_written"] = _write_evidence(result, evidence_dir)

    return result


def _write_evidence(result: dict[str, Any], evidence_dir: str | None) -> dict[str, str]:
    base = Path(evidence_dir) if evidence_dir else _repo_root() / EVIDENCE_DIR
    base.mkdir(parents=True, exist_ok=True)
    json_path = base / _PROOF_JSON
    md_path = base / _PROOF_MD
    json_path.write_text(json.dumps(result, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(result), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def _render_markdown(result: dict[str, Any]) -> str:
    gates = result["gates"]
    lines = [
        "# Phase 10 Prompt 01 — Contracts, Seeds & Policy Proof",
        "",
        f"**Status:** {result['overall_status']} · **proof_passed:** {result['proof_passed']}",
        f"· **generated_utc:** {result['generated_utc']}",
        "",
        f"- repo_sha: `{result['repo_sha']}`",
        f"- schema_version: {result['schema_version']} (no V41 migration in this prompt)",
        f"- contracts: {result['contract_count']} · seeds: {result['seed_count']}"
        f" · fixtures: {len(result['fixtures_validated'])}",
        "",
        "## Gates",
        "",
        "| Gate | Pass |",
        "| --- | --- |",
    ]
    lines += [f"| {name} | {value} |" for name, value in gates.items()]
    lines += [
        "",
        "## Seed versions",
        "",
    ]
    lines += [f"- `{name}`: {ver}" for name, ver in result["seed_versions"].items()]
    lines += [
        "",
        "## Fixtures validated",
        "",
    ]
    lines += [f"- {fid}" for fid in result["fixtures_validated"]]
    lines += [
        "",
        "## Guardrails",
        "",
        "Local-only; advisory candidates only; structured output validated against Pydantic"
        " contracts before any future write; high-stakes items are review signals, never"
        " determinations; every candidate requires >=1 source ref; no raw body/payload/prompt/"
        "response/URL/token/secret persisted; no Graph/Procore/email/calendar writeback.",
    ]
    if result["errors"]:
        lines += ["", "## Errors", ""] + [f"- {e}" for e in result["errors"]]
    if result["forbidden_findings"]:
        lines += ["", "## Forbidden-content findings", ""]
        lines += [f"- {f['artifact']}: {f['finding']}" for f in result["forbidden_findings"]]
    return "\n".join(lines) + "\n"
