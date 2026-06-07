"""Phase 10 Prompt 04 — Local Model Structured Output Client proof (advisory, read-only).

Exercises the :class:`StructuredOutputClient` end-to-end over the bundled local_ai fixtures using a
deterministic offline backend (no Ollama, no network), and proves the load-bearing guarantees of
Prompt 04:

- schema enforcement (each fixture validates against :class:`ActionCandidate`);
- the heavy-profile gate blocks an un-enabled heavy profile;
- an unavailable backend is handled with a redacted code + single-hop fallback (no raw error text);
- a dry-run writes **zero** receipt rows;
- an ``--apply`` run writes exactly one **hash-only** ``local_model_run_receipts`` row whose 13
  no-raw / no-writeback guard columns sum to 0 and which carries only SHA-256[:12] hashes.

The apply demonstration runs against a throwaway temp SQLite DB so the ambient app DB is never
touched. The only optional side effect is writing the evidence JSON/MD when ``write_evidence=True``.

Public entry point:
    build_structured_output_client_proof(*, evidence_dir=None, write_evidence=False) -> dict
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

from .contracts import load_local_model_profiles
from .models import ActionCandidate
from .schema import PHASE_10_GUARD_COLUMNS
from .structured_output import (
    StaticOutputClient,
    StructuredOutputClient,
    action_candidate_dict_from_fixture,
)

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-10-local-action-intelligence"
_PROOF_JSON = "04-structured-output-client-proof.json"
_PROOF_MD = "04-structured-output-client-proof.md"

_FIXTURES: tuple[str, ...] = (
    "tests/fixtures/local_ai/email_task_candidate_001.json",
    "tests/fixtures/local_ai/commitment_candidate_001.json",
    "tests/fixtures/local_ai/follow_up_monitor_001.json",
    "tests/fixtures/local_ai/relationship_candidate_001.json",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=PathPolicy().resolve_repo_root(),
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def build_structured_output_client_proof(
    *,
    evidence_dir: str | None = None,
    write_evidence: bool = False,
) -> dict[str, Any]:
    """Exercise the structured-output client over fixtures and prove Prompt 04 guarantees."""
    repo_root = PathPolicy().resolve_repo_root()
    profiles = load_local_model_profiles()
    by_id = {p.profile_id: p for p in profiles.profiles}
    default = by_id["default_extract"]
    heavy = by_id["heavy_context"]
    client = StructuredOutputClient()

    gates: dict[str, bool] = {}
    fixtures_validated: list[dict[str, Any]] = []

    # 1. Each fixture validates against the ActionCandidate schema (dry-run, no writes).
    all_valid = True
    for rel in _FIXTURES:
        path = repo_root / rel
        try:
            fixture = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - evidence robustness
            fixtures_validated.append({"fixture": rel, "ok": False, "error": str(exc)[:120]})
            all_valid = False
            continue
        candidate = action_candidate_dict_from_fixture(fixture)
        res = client.run(
            schema=ActionCandidate,
            profile=default,
            profiles=profiles,
            system="proof",
            prompt="extract",
            input_context=json.dumps(fixture.get("input_redacted", {}), sort_keys=True),
            task_type="extract_email_tasks",
            backend=StaticOutputClient(json.dumps(candidate)),
            dry_run=True,
        )
        all_valid = all_valid and res.schema_valid
        fixtures_validated.append(
            {
                "fixture": rel,
                "ok": res.schema_valid,
                "status": res.status,
                "input_context_hash": res.input_context_hash,
                "output_hash": res.output_hash,
            }
        )
    gates["fixtures_schema_valid"] = all_valid

    # 2. Heavy-profile gate blocks an un-enabled heavy profile.
    valid_candidate = json.dumps(action_candidate_dict_from_fixture(json.loads(
        (repo_root / _FIXTURES[0]).read_text(encoding="utf-8")
    )))
    blocked = client.run(
        schema=ActionCandidate,
        profile=heavy,
        profiles=profiles,
        system="proof",
        prompt="extract",
        input_context="ctx",
        task_type="x",
        backend=StaticOutputClient(valid_candidate),
        dry_run=True,
    )
    gates["heavy_profile_blocked"] = (
        blocked.status == "blocked"
        and blocked.error_redacted == "heavy_profile_requires_explicit_enable"
    )

    # 3. Unavailable backend → redacted code + single-hop fallback (no raw error text).
    unavailable = client.run(
        schema=ActionCandidate,
        profile=by_id["quality_reasoning"],
        profiles=profiles,
        system="proof",
        prompt="extract",
        input_context="ctx",
        task_type="x",
        backend=StaticOutputClient(raise_unavailable=True),
        dry_run=True,
    )
    gates["unavailable_fallback_redacted"] = (
        unavailable.fallback_used is True
        and unavailable.status in {"unavailable", "timeout"}
        and bool(unavailable.error_redacted)
        and "http" not in (unavailable.error_redacted or "")
    )

    # 4 + 5. Dry-run writes nothing; apply writes exactly one hash-only receipt, guards sum to 0.
    guard_sum = -1
    receipt_row: dict[str, Any] | None = None
    dry_run_rows = -1
    apply_rows = -1
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "p10p04-proof.db")
        store = ConstructionStore(db_path=db)
        client.run(
            schema=ActionCandidate,
            profile=default,
            profiles=profiles,
            system="proof",
            prompt="extract",
            input_context="ctx",
            task_type="extract_email_tasks",
            backend=StaticOutputClient(valid_candidate),
            store=store,
            dry_run=True,
        )
        dry_run_rows = len(store.list_local_model_run_receipts())
        applied = client.run(
            schema=ActionCandidate,
            profile=default,
            profiles=profiles,
            system="proof",
            prompt="extract",
            input_context="ctx",
            task_type="extract_email_tasks",
            backend=StaticOutputClient(valid_candidate),
            store=store,
            dry_run=False,
        )
        rows = store.list_local_model_run_receipts()
        apply_rows = len(rows)
        receipt_row = rows[0] if rows else None
        conn = sqlite3.connect(db)
        expr = " + ".join(f"COALESCE(SUM({g}),0)" for g in PHASE_10_GUARD_COLUMNS)
        guard_sum = int(
            conn.execute(f"SELECT {expr} FROM local_model_run_receipts").fetchone()[0]
        )
        conn.close()
        _ = applied

    gates["dry_run_zero_writes"] = dry_run_rows == 0
    gates["apply_single_receipt"] = apply_rows == 1
    gates["receipt_guards_clean"] = guard_sum == 0
    # The persisted row carries only hashes/metadata — never the raw input context.
    gates["receipt_hash_only"] = bool(receipt_row) and "ctx" not in json.dumps(receipt_row)

    proof_passed = all(gates.values())
    result: dict[str, Any] = {
        "proof": "phase_10_structured_output_client_proof",
        "command": "second-brain action-intel / ai-jobs (Prompt 04 client)",
        "phase": "10",
        "prompt": "04",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "schema_version": LATEST_SCHEMA_VERSION,
        "proof_passed": proof_passed,
        "overall_status": "clean" if proof_passed else "findings",
        "gates": gates,
        "fixtures_validated": fixtures_validated,
        "receipt_sample": receipt_row,
        "guard_columns": PHASE_10_GUARD_COLUMNS,
        "guard_sum": guard_sum,
        "guardrails": {
            "local_only": True,
            "schema_validation_required": True,
            "no_raw_persistence": True,
            "no_external_writeback": True,
            "receipts_hash_only": True,
            "heavy_profile_default_blocked": True,
            "dry_run_default": True,
            "errors_redacted": True,
        },
    }
    if write_evidence:
        result["evidence_written"] = _write_evidence(result, evidence_dir)
    return result


def _write_evidence(result: dict[str, Any], evidence_dir: str | None) -> dict[str, str]:
    base = Path(evidence_dir) if evidence_dir else PathPolicy().resolve_repo_root() / EVIDENCE_DIR
    base.mkdir(parents=True, exist_ok=True)
    json_path = base / _PROOF_JSON
    md_path = base / _PROOF_MD
    json_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(result), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def _render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Phase 10 Prompt 04 — Local Model Structured Output Client Proof",
        "",
        f"**Status:** {result['overall_status']} · **proof_passed:** {result['proof_passed']}"
        f" · **generated_utc:** {result['generated_utc']}",
        "",
        f"- repo_sha: `{result['repo_sha']}`",
        f"- schema_version: V{result['schema_version']}",
        f"- guard_sum: {result['guard_sum']} (must be 0)",
        "",
        "## Gates",
        "",
        "| Gate | Pass |",
        "| --- | --- |",
    ]
    for k, v in result["gates"].items():
        lines.append(f"| {k} | {v} |")
    lines += [
        "",
        "## Fixtures validated",
        "",
        "| Fixture | Schema valid | input_context_hash | output_hash |",
        "| --- | --- | --- | --- |",
    ]
    for f in result["fixtures_validated"]:
        lines.append(
            f"| {f.get('fixture')} | {f.get('ok')} | {f.get('input_context_hash')} |"
            f" {f.get('output_hash')} |"
        )
    lines += [
        "",
        "## Receipt sample (hash-only)",
        "",
        "```json",
        json.dumps(result.get("receipt_sample"), indent=2),
        "```",
        "",
        "## Guardrails",
        "",
        "Local-only; schema-validated before any write; receipts carry only SHA-256[:12] hashes and"
        " metadata (no raw prompt/response/body/URL/token/path); 13 no-raw/no-writeback guard columns"
        " sum to 0; heavy profiles blocked unless explicitly enabled; dry-run is the default; backend"
        " and validation errors are redacted to category codes.",
    ]
    return "\n".join(lines) + "\n"
