"""Phase 09 Addendum (Daily Brief V2) — closeout & handoff bundle (Prompt 06).

Aggregates the addendum's closeout facts into a metadata-only report: git branch / commit / files
changed, schema version (unchanged by the addendum), packet version, the corrected advisory output
path, the V2 executive-render-quality result (including the rejected internal-commentary fixture),
record-level enrichment coverage + detail-unavailable counts (over a deterministic seeded V2 packet),
a summary of the captured validation-command runs, remaining limitations, and the recommended next
improvement. Read-only; no-raw-gated; no source-system writeback; no production-readiness claim.

Public entry point:
  build_daily_brief_v2_closeout(*, brief_date, validation_dir=None, evidence_dir=None,
                                write_evidence=True) -> dict
CLI: hb-assistant second-brain daily-brief v2-closeout --json
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

from ..financial_review_routing import _assert_no_raw

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-addendum-daily-brief-v2"
_CLOSEOUT_JSON = "daily-brief-v2-closeout.json"
_CLOSEOUT_MD = "daily-brief-v2-closeout.md"

# Prompt 00 repo-truth baseline (start of the addendum) — used to scope files-changed.
_ADDENDUM_BASELINE_SHA = "76f515121478ce53a65699295d5c458aa9523979"

# Prefixes that belong to the Daily Brief V2 addendum (files-changed is filtered to these).
_ADDENDUM_PREFIXES: tuple[str, ...] = (
    "src/hb_assistant/construction/second_brain/daily_brief/",
    "src/hb_assistant/construction/second_brain/mcp/",
    "src/hb_assistant/construction/second_brain/contracts.py",
    "src/hb_assistant/cli/second_brain.py",
    "src/hb_assistant/resources/json/phase_09_daily_brief_handoff_packet_v2_contract.json",
    "resources/templates/claude_daily_brief_",
    "docs/architecture/178-",
    "docs/architecture/179-",
    "docs/architecture/180-",
    "docs/architecture/181-",
    "docs/architecture/182-",
    "docs/architecture/183-",
    "docs/evidence/construction-intelligence-phase-09-addendum-daily-brief-v2/",
    "tests/test_phase_09_daily_brief_packet_v2.py",
    "tests/test_phase_09_daily_brief_v2_quality.py",
    "tests/test_phase_09_daily_brief_v2_closeout.py",
)

_LIMITATIONS: tuple[str, ...] = (
    "RFIs / submittals / punch / procurement remain detail-unavailable (no dedicated readers yet); "
    "they emit explicit detail_available=false with detail_gap_reason='dedicated_reader_not_available'.",
    "Responsible-party / vendor names and a stored days_open are not persisted; rendered as null with "
    "per-record reasons.",
    "Semantic retrieval is advisory only and never authoritative; accepted memory never overrides "
    "source truth.",
    "LlamaIndex local embedding is optional: real --apply / semantic fail-closed with honest reasons "
    "without the 'retrieval-local' extra.",
    "production_readiness is false; the rendered narrative is advisory and is never imported into "
    "accepted memory / vector index / source manifest / source-linked proof.",
)

_NEXT_IMPROVEMENT = {
    "title": "Phase 10 — Operator Workflow Delivery and UX Hardening",
    "objective": "Make the validated daily brief and retrieval intelligence easy to run, inspect, "
    "and act on.",
    "scope": [
        "One-command daily workflow: generate packet → render brief → save to Obsidian → emit "
        "receipt → run proof → summarize status.",
        "Operator-friendly output: concise CLI summaries, stable output paths, easy markdown, reduced "
        "JSON inspection.",
        "Review workflow: review-required queue, stale/unknown queue, metadata-only source-linked "
        "drilldown, accepted-memory review.",
        "Quality dashboard: usefulness score, source-coverage trend, unsupported-claim risk trend, "
        "detail-available vs detail-unavailable trend.",
    ],
}

_PASS_KEYS = ("proof_passed", "passed", "gates_passed", "ok")


class DailyBriefCloseoutError(RuntimeError):
    """Raised when the closeout bundle cannot be assembled (fail-closed)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _git(args: list[str]) -> str:
    try:
        out = subprocess.check_output(
            ["git", *args], cwd=_repo_root(), stderr=subprocess.DEVNULL, timeout=10
        )
        return out.decode("utf-8").strip()
    except Exception:
        return ""


def _git_facts() -> dict[str, Any]:
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
    sha = _git(["rev-parse", "HEAD"]) or "unknown"
    changed_raw = _git(["diff", "--name-only", f"{_ADDENDUM_BASELINE_SHA}..HEAD"])
    all_changed = [line for line in changed_raw.splitlines() if line.strip()]
    addendum_files = sorted(f for f in all_changed if f.startswith(_ADDENDUM_PREFIXES))
    return {
        "branch": branch,
        "commit_sha": sha,
        "addendum_baseline_sha": _ADDENDUM_BASELINE_SHA,
        "files_changed": addendum_files,
        "files_changed_count": len(addendum_files),
        "note": "Files-changed is scoped to Daily Brief V2 addendum prefixes; the shared 'main' branch "
        "also carried parallel-workstream (FastAPI dashboard) commits in the same range.",
    }


def _is_record_section(value: Any) -> bool:
    return isinstance(value, dict) and "detail_available" in value


def _enrichment_coverage() -> dict[str, Any]:
    """Record-level enrichment coverage over a deterministic, representative seeded V2 packet."""
    from .packet import _seed_v2_enrichment_db, build_daily_brief_packet_v2

    with tempfile.TemporaryDirectory() as tmp:
        db = f"{tmp}/closeout-seed.sqlite3"
        _seed_v2_enrichment_db(db)
        packet = build_daily_brief_packet_v2(brief_date="2026-06-02", project_key="P1", db_path=db)

    render = packet.get("render_payload", {})
    governance = packet.get("governance_metadata", {})
    packet_version = (
        governance.get("packet_version")
        or packet.get("packet_version")
        or "DailyBriefHandoffPacketV2"
    )

    sections: dict[str, Any] = {}
    detail_available_true = 0
    detail_unavailable = 0
    records_total = 0
    gap_reasons: dict[str, int] = {}
    for name, value in render.items():
        if not _is_record_section(value):
            continue
        available = value.get("detail_available") is True
        count = int(value.get("count") or 0)
        sections[name] = {
            "detail_available": available,
            "count": count,
            "detail_gap_reason": value.get("detail_gap_reason"),
        }
        if available:
            detail_available_true += 1
            records_total += count
        else:
            detail_unavailable += 1
            reason = value.get("detail_gap_reason") or "unspecified"
            gap_reasons[reason] = gap_reasons.get(reason, 0) + 1

    return {
        "basis": "representative (seeded enrichment db)",
        "packet_version": packet_version,
        "record_section_count": len(sections),
        "detail_available_true": detail_available_true,
        "detail_unavailable": detail_unavailable,
        "records_total": records_total,
        "detail_gap_reasons": gap_reasons,
        "sections": sections,
    }


def _extract_pass(obj: Any) -> bool | None:
    if isinstance(obj, dict):
        for key in _PASS_KEYS:
            if key in obj and isinstance(obj[key], bool):
                return obj[key]
    return None


def _validation_runs(validation_dir: str | Path | None) -> dict[str, Any]:
    if validation_dir is None:
        return {"captured": False, "runs": {}}
    base = Path(validation_dir)
    if not base.exists():
        return {"captured": False, "runs": {}}
    runs: dict[str, Any] = {}
    for path in sorted(base.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            runs[path.stem] = {"status": "unreadable", "file": path.name}
            continue
        passed = _extract_pass(data)
        runs[path.stem] = {
            "passed": passed,
            "status": "captured" if passed is None else ("passed" if passed else "failed"),
            "file": path.name,
        }
    return {"captured": True, "runs": runs, "run_count": len(runs)}


def build_daily_brief_v2_closeout(
    *,
    brief_date: str = "2026-06-06",
    validation_dir: str | Path | None = None,
    evidence_dir: str | None = None,
    write_evidence: bool = True,
) -> dict[str, Any]:
    """Assemble the Daily Brief V2 closeout/handoff bundle (metadata-only, read-only, no-raw-gated)."""
    from .output_receipt import resolve_rendered_brief_path
    from .rendered_quality import build_daily_brief_v2_quality_proof

    quality = build_daily_brief_v2_quality_proof(write_evidence=False)
    coverage = _enrichment_coverage()
    git_facts = _git_facts()

    output_path = f"<vault>/Work/Daily Brief/{brief_date}-daily-brief.md"
    # Resolve the real path for the redacted parent (kept out of the report body).
    _ = resolve_rendered_brief_path(brief_date)

    fixtures = quality["fixtures"]
    daily_brief_gates = {
        "v2_render_quality_passed": bool(quality["proof_passed"]),
        "full_detail_passed": bool(fixtures["full_detail"]["passed"]),
        "detail_unavailable_passed": bool(fixtures["detail_unavailable"]["passed"]),
        "rejected_internal_rejected": fixtures["rejected_internal"]["passed"] is False,
    }
    closeout_complete = all(daily_brief_gates.values())

    closeout: dict[str, Any] = {
        "closeout": "phase_09_addendum_daily_brief_v2",
        "package": "HB_Construction_Intelligence_Phase_09_Addendum_Daily_Brief_V2_"
        "Executive_Utility_Hardening",
        "prompt": "06",
        "version": "1.5.0-phase-09-addendum-v2",
        "command": "second-brain daily-brief v2-closeout",
        "generated_utc": _now(),
        "closeout_complete": closeout_complete,
        "branch": git_facts["branch"],
        "commit_sha": git_facts["commit_sha"],
        "files_changed": git_facts["files_changed"],
        "files_changed_count": git_facts["files_changed_count"],
        "files_changed_note": git_facts["note"],
        "schema_version": LATEST_SCHEMA_VERSION,
        "schema_changed_by_addendum": False,
        "packet_version": coverage["packet_version"],
        "output_path": output_path,
        "output_path_filename_convention": "YYYY-MM-DD-daily-brief.md",
        "v2_render_quality": {
            "passed": bool(quality["proof_passed"]),
            "check_count": quality["check_count"],
            "max_brief_chars": quality["max_brief_chars"],
            "full_detail": fixtures["full_detail"],
            "detail_unavailable": fixtures["detail_unavailable"],
            "rejected_internal": fixtures["rejected_internal"],
        },
        "record_level_enrichment_coverage": coverage,
        "detail_unavailable_counts": {
            "detail_unavailable_sections": coverage["detail_unavailable"],
            "detail_gap_reasons": coverage["detail_gap_reasons"],
        },
        "daily_brief_gates": daily_brief_gates,
        "validation_runs": _validation_runs(validation_dir),
        "acceptance_test": {
            "standard": "A construction executive can read the brief in under 3 minutes and understand "
            "yesterday, today's agenda, next-7-day deadlines, what needs attention, and what to focus "
            "on, without reading packet/proof/governance internals.",
            "demonstrated_by": "daily-brief-v2-golden-full-detail.md (passes all "
            f"{quality['check_count']} executive-quality checks)",
            "met": closeout_complete,
        },
        "limitations": list(_LIMITATIONS),
        "next_improvement": _NEXT_IMPROVEMENT,
        "guardrails": {
            "advisory_only": True,
            "read_only": True,
            "metadata_only": True,
            "no_raw": True,
            "no_writeback": True,
            "rendered_text_not_imported_to_trusted_surfaces": True,
            "production_readiness": False,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(closeout, indent=2, default=str)
        _assert_no_raw(serialized, "daily-brief v2 closeout json")
        (out_dir / _CLOSEOUT_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_closeout_md(closeout)
        _assert_no_raw(markdown, "daily-brief v2 closeout markdown")
        (out_dir / _CLOSEOUT_MD).write_text(markdown, encoding="utf-8")
        closeout["closeout_path"] = str(out_dir / _CLOSEOUT_JSON)
        closeout["closeout_md_path"] = str(out_dir / _CLOSEOUT_MD)

    return closeout


def _render_closeout_md(c: dict[str, Any]) -> str:
    cov = c["record_level_enrichment_coverage"]
    runs = c["validation_runs"].get("runs", {})
    lines = [
        "# Daily Brief V2 — Closeout & Handoff (Prompt 06)",
        "",
        f"- package: {c['package']}",
        f"- version: {c['version']}",
        f"- generated_utc: {c['generated_utc']}",
        f"- closeout_complete: {c['closeout_complete']}",
        "",
        "## Repo",
        "",
        f"- branch: {c['branch']}",
        f"- commit_sha: {c['commit_sha']}",
        f"- files_changed (addendum-scoped): {c['files_changed_count']}",
        f"- schema_version: V{c['schema_version']} (changed_by_addendum: {c['schema_changed_by_addendum']})",
        f"- packet_version: {c['packet_version']}",
        f"- output_path: {c['output_path']}",
        "",
        "## V2 render quality",
        "",
        f"- passed: {c['v2_render_quality']['passed']} "
        f"(check_count={c['v2_render_quality']['check_count']})",
        f"- full_detail: passed={c['v2_render_quality']['full_detail']['passed']}",
        f"- detail_unavailable: passed={c['v2_render_quality']['detail_unavailable']['passed']}",
        f"- rejected_internal: passed={c['v2_render_quality']['rejected_internal']['passed']} "
        f"(rejected as expected)",
        "",
        "## Record-level enrichment coverage (representative, seeded)",
        "",
        f"- record sections: {cov['record_section_count']}; detail_available: "
        f"{cov['detail_available_true']}; detail_unavailable: {cov['detail_unavailable']}",
        f"- records (available sections): {cov['records_total']}",
        f"- detail_gap_reasons: {cov['detail_gap_reasons']}",
        "",
        "## Validation runs (captured)",
        "",
    ]
    if runs:
        for name, rep in runs.items():
            lines.append(f"- {name}: {rep.get('status')}")
    else:
        lines.append("- (no validation_dir provided to this run)")
    lines += [
        "",
        "## Acceptance test",
        "",
        f"- met: {c['acceptance_test']['met']}",
        f"- {c['acceptance_test']['standard']}",
        f"- demonstrated by: {c['acceptance_test']['demonstrated_by']}",
        "",
        "## Remaining limitations",
        "",
        *[f"- {limitation}" for limitation in c["limitations"]],
        "",
        "## Recommended next improvement",
        "",
        f"- {c['next_improvement']['title']} — {c['next_improvement']['objective']}",
        *[f"  - {item}" for item in c["next_improvement"]["scope"]],
        "",
    ]
    return "\n".join(lines)
