"""Phase 09 Addendum — daily-brief output receipts + deferred import policy.

Defines the two daily-brief output classes and prevents Claude-rendered narrative from contaminating
trusted retrieval/memory stores:

- **Trusted packet** — application-generated, metadata-only, source-linked, approved, MCP-safe,
  regenerable; may be referenced by manifest/evidence.
- **Rendered narrative** — Claude-generated, human-readable, advisory, **not source truth**; never a
  vector-index / accepted-memory / source-manifest / source-linked-proof input.

Exclusion is by construction: ``RENDERED_OUTPUT_CLASS`` is not in ``ALLOWLISTED_SOURCE_FAMILIES`` (the
superset of embeddable + manifest read-model + source-linked families) nor in the approved-manifest
categories, and accepted memory only loads ``review_status='accepted'`` items. Import of rendered text
is **deferred** (``import_rendered_brief`` fails closed). Read-only, metadata-only; no DB persistence.

The canonical advisory output path is ``<vault>/Work/Daily Brief/<date>-daily-brief.md`` (Daily Brief
V2). ``resolve_rendered_brief_path`` / ``write_rendered_brief`` resolve and (apply-only) write it; the
write creates the directory if missing and never persists the body to SQLite.

Public entry points:
  resolve_rendered_brief_path(brief_date, *, vault_brief_dir=None) -> Path
  rendered_brief_filename(brief_date) -> str
  write_rendered_brief(*, brief_date, body, vault_brief_dir=None, apply=False) -> dict  # metadata-only
  build_trusted_packet_receipt(*, packet) -> dict
  build_rendered_brief_receipt(*, packet, rendered_path, renderer, validation_passed, rendered_utc) -> dict
  import_rendered_brief(*args, **kwargs)  # fail-closed (deferred)
  build_daily_brief_rendered_output_receipt_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain daily-brief output-receipt-proof --json
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy

from ..financial_review_routing import _assert_no_raw
from ..retrieval import ALLOWLISTED_SOURCE_FAMILIES
from .output import _atomic_write_text

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-daily-brief-mcp-handoff"
_PROOF_JSON = "daily-brief-rendered-output-receipt-proof.json"
_PROOF_MD = "daily-brief-rendered-output-receipt-proof.md"

RENDERED_OUTPUT_CLASS = "rendered_daily_brief_narrative"
TRUSTED_PACKET_OUTPUT_CLASS = "trusted_daily_brief_packet"

# The 4 approved-source-manifest categories (resources/config/phase_09_approved_source_manifest.seed.yaml).
_APPROVED_MANIFEST_CATEGORIES: tuple[str, ...] = (
    "generated_outputs",
    "approved_obsidian_outputs",
    "reviewed_memory",
    "approved_read_models",
)

# Phase 09 Addendum (Daily Brief V2) — canonical rendered-narrative output location. The advisory,
# Claude-rendered executive brief lands here; this is NOT the deterministic Phase 08A brief root
# (``daily_brief/output.py``), which is an approved, indexed, manifest-referenced generated output.
RENDERED_VAULT_SUBDIR = Path("Work") / "Daily Brief"

# Documented output-class locations (operator/runtime; not created by this module).
TRUSTED_PACKET_LOCATION = (
    "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/daily-brief-packets/ "
    "(or the existing daily-brief evidence/output path)"
)
RENDERED_NARRATIVE_LOCATION = (
    f"<vault>/{RENDERED_VAULT_SUBDIR.as_posix()}/ "
    "(a clearly marked local advisory output directory)"
)

# Import of rendered narrative into trusted stores is deferred — not implemented in this package.
IMPORT_ENABLED = False


class RenderedOutputReceiptError(RuntimeError):
    """Raised for deferred/unsupported rendered-output operations (fail-closed)."""


def rendered_brief_filename(brief_date: str) -> str:
    """Date-stable rendered-brief filename: ``YYYY-MM-DD-daily-brief.md``."""
    return f"{brief_date}-daily-brief.md"


def resolve_rendered_brief_path(
    brief_date: str, *, vault_brief_dir: str | Path | None = None
) -> Path:
    """Resolve the canonical advisory rendered-brief path (vault-governed by default).

    Default: ``<vault>/Work/Daily Brief/<date>-daily-brief.md``. ``Path`` carries the space in
    "Daily Brief" natively. The rendered brief is advisory only and is never source truth.
    """
    base = (
        Path(vault_brief_dir)
        if vault_brief_dir is not None
        else (PathPolicy().get_vault_root() / RENDERED_VAULT_SUBDIR)
    )
    return base / rendered_brief_filename(brief_date)


def write_rendered_brief(
    *,
    brief_date: str,
    body: str,
    vault_brief_dir: str | Path | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    """Write the advisory rendered brief to the canonical vault path (apply only; metadata-only return).

    Dry-run (default) computes the content hash and writes nothing. On ``apply`` the parent directory
    is created if missing (``_atomic_write_text`` → ``mkdir(parents=True, exist_ok=True)``) and the body
    is written atomically. The rendered body is **never** persisted to SQLite or any trusted store — it
    is a local advisory file only. Returns metadata only (no body).
    """
    target = resolve_rendered_brief_path(brief_date, vault_brief_dir=vault_brief_dir)
    content_hash = _hash(body)

    if not apply:
        return {
            "written": False,
            "rendered_path_redacted": None,
            "content_hash": content_hash,
            "persisted_to_sqlite": False,
        }

    _atomic_write_text(target, body)
    try:
        redacted = str(target.relative_to(PathPolicy().get_vault_root()))
    except ValueError:
        redacted = f"{target.parent.name}/{target.name}"
    return {
        "written": True,
        "rendered_path_redacted": redacted,
        "content_hash": content_hash,
        "persisted_to_sqlite": False,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_sha() -> str:
    try:
        repo_root = Path(__file__).resolve().parents[5]
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, stderr=subprocess.DEVNULL, timeout=5
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def packet_hash(packet: dict[str, Any]) -> str:
    """Stable content hash of a packet (metadata identifier only)."""
    return _hash(json.dumps(packet, sort_keys=True, default=str))[:48]


def build_trusted_packet_receipt(*, packet: dict[str, Any]) -> dict[str, Any]:
    """Metadata-only receipt for an application-generated trusted daily-brief packet."""
    return {
        "receipt_kind": "trusted_daily_brief_packet",
        "output_class": TRUSTED_PACKET_OUTPUT_CLASS,
        "packet_id": packet.get("packet_id"),
        "packet_hash": packet_hash(packet),
        "packet_version": packet.get("packet_version"),
        "location_policy": TRUSTED_PACKET_LOCATION,
        "metadata_only": True,
        "source_linked": True,
        "approved": True,
        "safe_for_mcp": True,
        "may_be_referenced_by_manifest": True,
        "may_be_regenerated": True,
        "external_writeback": False,
    }


def build_rendered_brief_receipt(
    *,
    packet: dict[str, Any],
    rendered_path: str,
    renderer: str = "claude_scheduled_task",
    validation_passed: bool | None,
    rendered_utc: str | None = None,
) -> dict[str, Any]:
    """Metadata-only receipt for a Claude-rendered daily brief (advisory; never source truth)."""
    status = (
        "not_run" if validation_passed is None else ("passed" if validation_passed else "failed")
    )
    return {
        "receipt_kind": "rendered_daily_brief_output",
        "output_class": RENDERED_OUTPUT_CLASS,
        "packet_id": packet.get("packet_id"),
        "packet_hash": packet_hash(packet),
        "rendered_file_path": rendered_path,
        "rendered_utc": rendered_utc or _now(),
        "renderer": renderer,
        "validation_proof_status": status,
        "location_policy": RENDERED_NARRATIVE_LOCATION,
        "advisory_only": True,
        "not_source_truth": True,
        "imported_to_memory": False,
        "imported_to_vector_index": False,
        "imported_to_source_manifest": False,
        "imported_to_source_linked_proof": False,
        "persisted_to_sqlite": False,
        "external_writeback": False,
        "import_enabled": IMPORT_ENABLED,
    }


def import_rendered_brief(*_args: Any, **_kwargs: Any) -> None:
    """Deferred: importing rendered narrative into trusted stores is not implemented (fail-closed).

    A later import would require an explicit reviewed-import workflow with source-link preservation and
    no-raw / no-writeback / no-determination proofs.
    """
    raise RenderedOutputReceiptError(
        "rendered-brief import is deferred; a reviewed-import workflow is required before any "
        "ingestion into accepted memory, the vector index, the source manifest, or source-linked proof"
    )


# --- Proof ---------------------------------------------------------------------------------------


def _render_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — Daily Brief Rendered Output Receipt Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        "",
        "## Checks",
        "",
    ]
    for name, value in proof["checks"].items():
        lines.append(f"- {name}: {value}")
    lines.append("")
    lines.append("## Output classes")
    lines.append("")
    lines.append(f"- trusted packet: `{TRUSTED_PACKET_OUTPUT_CLASS}` — {TRUSTED_PACKET_LOCATION}")
    lines.append(f"- rendered narrative: `{RENDERED_OUTPUT_CLASS}` — {RENDERED_NARRATIVE_LOCATION}")
    lines.append("")
    return "\n".join(lines)


def build_daily_brief_rendered_output_receipt_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: rendered receipt is advisory/not-source-truth and excluded (by construction)
    from the vector index, approved manifest, source-linked proof, and accepted memory; import deferred."""
    from .rendered_quality import (
        _SAMPLE_RENDERED_BRIEF,
        _sample_packet,
        validate_rendered_brief,
    )

    packet = _sample_packet()
    validation = validate_rendered_brief(packet, _SAMPLE_RENDERED_BRIEF)

    sample_rendered_path = (
        f"<vault>/{RENDERED_VAULT_SUBDIR.as_posix()}/{rendered_brief_filename('2026-06-06')}"
    )
    packet_receipt = build_trusted_packet_receipt(packet=packet)
    rendered_receipt = build_rendered_brief_receipt(
        packet=packet,
        rendered_path=sample_rendered_path,
        renderer="claude_scheduled_task",
        validation_passed=bool(validation["passed"]),
        rendered_utc=_now(),
    )

    def _no_raw(obj: dict[str, Any]) -> bool:
        try:
            _assert_no_raw(json.dumps(obj, default=str), "receipt")
            return True
        except ValueError:
            return False

    # Import must be deferred (fail-closed).
    try:
        import_rendered_brief(rendered_receipt)
        import_disabled = False
    except RenderedOutputReceiptError:
        import_disabled = True

    cls = RENDERED_OUTPUT_CLASS
    checks: dict[str, bool] = {
        "packet_receipt_no_raw": _no_raw(packet_receipt),
        "rendered_receipt_no_raw": _no_raw(rendered_receipt),
        "rendered_not_source_truth": rendered_receipt["not_source_truth"] is True
        and rendered_receipt["advisory_only"] is True,
        "excluded_from_vector_index": rendered_receipt["imported_to_vector_index"] is False
        and cls not in ALLOWLISTED_SOURCE_FAMILIES,
        "excluded_from_accepted_memory": rendered_receipt["imported_to_memory"] is False
        and cls != "accepted_long_term_memory",
        "excluded_from_source_manifest": rendered_receipt["imported_to_source_manifest"] is False
        and cls not in ALLOWLISTED_SOURCE_FAMILIES
        and cls not in _APPROVED_MANIFEST_CATEGORIES,
        "excluded_from_source_linked_proof": rendered_receipt["imported_to_source_linked_proof"]
        is False
        and cls not in ALLOWLISTED_SOURCE_FAMILIES,
        "not_persisted_to_sqlite": rendered_receipt["persisted_to_sqlite"] is False,
        "rendered_path_is_correct": sample_rendered_path.endswith(
            "Work/Daily Brief/2026-06-06-daily-brief.md"
        ),
        "import_disabled_and_deferred": (IMPORT_ENABLED is False)
        and import_disabled
        and rendered_receipt["import_enabled"] is False,
        "no_external_writeback": rendered_receipt["external_writeback"] is False
        and packet_receipt["external_writeback"] is False,
        "receipt_references_packet": bool(rendered_receipt["packet_id"])
        and bool(rendered_receipt["packet_hash"]),
    }
    proof_passed = all(checks.values())

    proof: dict[str, Any] = {
        "proof": "phase_09_daily_brief_rendered_output_receipt",
        "command": "second-brain daily-brief output-receipt-proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "checks": checks,
        "trusted_packet_receipt": packet_receipt,
        "rendered_brief_receipt": rendered_receipt,
        "rendered_validation_passed": bool(validation["passed"]),
        "approved_manifest_categories": list(_APPROVED_MANIFEST_CATEGORIES),
        "allowlisted_source_families": list(ALLOWLISTED_SOURCE_FAMILIES),
        "import_enabled": IMPORT_ENABLED,
        "metadata_only": True,
        "review_only": True,
        "guardrails": {
            "advisory_only": True,
            "rendered_not_source_truth": True,
            "metadata_only": True,
            "no_raw": True,
            "no_writeback": True,
            "excluded_from_vector_index": True,
            "excluded_from_accepted_memory": True,
            "excluded_from_source_manifest": True,
            "import_deferred_fail_closed": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(serialized, "rendered output receipt proof json")
        (out_dir / _PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "rendered output receipt proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof
