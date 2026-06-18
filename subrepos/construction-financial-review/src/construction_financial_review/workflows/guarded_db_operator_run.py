"""Phase 12 — controlled guarded DB operator-run package (operator handoff).

Closes the gap Phase 11 left open: Phase 11 *proves* an operator can build a non-live temp v59 DB
from explicit Tropical source data and pass the Phase 10 readiness gate, but a passing rehearsal is
only evidence — nothing yet names *which* DB-backed artifacts are approved for guarded use, nor binds
them to the full safety/provenance chain. Phase 12 produces one deterministic operator handoff:

    explicit Tropical source package -> Phase 11 rehearsal (temp v59 DB + projection + Phase 10
    readiness + Phase 9 parity) -> validate the nested DB-backed artifacts -> deterministic guarded
    DB operator-run manifest naming the approved context/analysis chain and the evidence chain.

It is a handoff, not a default flip: it changes no production default, makes no DB-backed read or
package resolution the default, removes no file-backed path, generates no final integrated CSV, runs
no intelligence/comprehensive/probability/monthly/model-controls/LLM workflow, and adds no schema.

CFR-only: it reuses Phase 11 (rehearsal), Phase 10/Phase 9 report OUTPUTS (read back from disk), and
the Phase 8 package-resolution helpers; it reimplements none of temp-DB prep, projection, parity,
readiness, or package resolution. The only ``hb_assistant`` touchpoint is a lazy, fail-closed
live-DB check on an EXPLICIT ``db_path`` (Phase 11 enforces the authoritative DB safety again).

Refusal vs decision (fail closed):
  - unsafe / missing / ambiguous INPUTS, OR any structural/provenance inconsistency discovered AFTER
    a passing rehearsal (missing nested report, decision mismatch, wrong DB-mode semantics, chain
    mismatch, artifact path escape, live-root/live-DB risk) -> ``GuardedDbOperatorRunError``;
  - Phase 11 completing with failed/not-ready evidence is a successful operator-run OUTCOME
    (``status='not_ready'``), not a refusal — after a *passed* rehearsal those inconsistencies are
    impossible, so we fail closed rather than soft-downgrade.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..common.package_resolution import (
    PackageResolutionError,
    read_package_chain_manifest,
    resolve_explicit_package,
)
from .db_cutover_readiness import REQUIRED_SOURCE_DOMAIN_TABLES
from .temp_db_readiness_rehearsal import (
    REQUIRED_SCHEMA_VERSION,
    TempDbRehearsalError,
    run_temp_db_readiness_rehearsal,
)

SUPPORTED_PROJECT_KEY = "tropical"
MANIFEST_SCHEMA_VERSION = 1
MANIFEST_NAME = "guarded_db_operator_run_manifest.json"

DECISION_APPROVED = "approved_for_guarded_db_context_analysis_use"
DECISION_NOT_READY = "not_ready"
READINESS_DECISION_READY = "ready_for_guarded_operator_use"

# Controlled-safety guard only (mirrors the generators' default Synology root); NOT an authoritative
# environment resolver. Monkeypatched in tests; Phases 8-11 enforce their own (identical) guard, this
# one fails the operator-run preflight early.
_LIVE_ROOT = Path(
    "/Users/bobbyfetting/Library/CloudStorage/SynologyDrive-BFmacSync/Work/"
    "NAS - HB/Projects/2023/TWN - NAS/30_Financials/Forecasts/Data/2026-June"
)


class GuardedDbOperatorRunError(RuntimeError):
    """Raised when a guarded operator run is refused (fail closed; no soft fallback)."""


def _is_under(path: Path, root: Path) -> bool:
    """True when ``path`` equals or is nested under ``root`` (resolved, non-strict)."""
    rp = Path(path).expanduser().resolve(strict=False)
    rr = Path(root).expanduser().resolve(strict=False)
    return rp == rr or rp.is_relative_to(rr)


def _same_path(a: Path, b: Path) -> bool:
    return Path(a).expanduser().resolve(strict=False) == Path(b).expanduser().resolve(strict=False)


def _write_json_deterministic(path: Path, obj: dict) -> Path:
    """Write sorted-key, indented JSON with a trailing newline (no wall-clock); return the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _refuse_if_live_db(db_path: Path) -> None:
    """Fail closed if an EXPLICIT ``db_path`` is the live/default DB (or unresolvable).

    Imports the source-domain MODULE lazily and calls ``is_live_db_path`` via the module reference
    (not a name bound at import time) so tests can monkeypatch the safety behavior.
    """
    try:
        from hb_assistant.construction.forecast import source_domain_engine
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise GuardedDbOperatorRunError(
            f"cannot verify db_path against the live DB; hb_assistant unavailable: {exc}"
        ) from exc
    if source_domain_engine.is_live_db_path(Path(db_path)):
        raise GuardedDbOperatorRunError(
            f"db_path resolves to the live/default DB (or is unresolvable): {db_path}"
        )


def _load_json(path: Path, *, what: str) -> dict:
    """Read a nested evidence JSON file; fail closed on missing/unreadable/non-object content."""
    p = Path(path)
    if not p.is_file():
        raise GuardedDbOperatorRunError(f"{what} not found (broken evidence chain): {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GuardedDbOperatorRunError(f"{what} is not readable JSON: {p} ({exc})") from exc
    if not isinstance(data, dict):
        raise GuardedDbOperatorRunError(f"{what} is not a JSON object: {p}")
    return data


def _validated_artifact(*, raw_path: Any, work_root: Path, what: str) -> Path:
    """Resolve+validate one approved DB-backed artifact path (existence, work-root, live-root)."""
    if not raw_path:
        raise GuardedDbOperatorRunError(f"{what} is missing from the DB-mode report")
    path = Path(str(raw_path))
    if not path.exists():
        raise GuardedDbOperatorRunError(f"{what} does not exist (broken evidence chain): {path}")
    if not _is_under(path, work_root):
        raise GuardedDbOperatorRunError(
            f"{what} resolves outside the work root (refused): {path} not under {work_root}"
        )
    if _is_under(path, _LIVE_ROOT):
        raise GuardedDbOperatorRunError(
            f"{what} resolves at/under the live forecast root (refused): {path}"
        )
    return path


def run_guarded_db_operator_run(
    *,
    source_package: Path,
    work_root: Path,
    context_stamp: str,
    db_path: Path | None = None,
    project_key: str = SUPPORTED_PROJECT_KEY,
) -> dict[str, Any]:
    """Run the controlled chain and emit a guarded DB operator-run manifest.

    Lightweight preflight fails closed (``GuardedDbOperatorRunError``) BEFORE creating any output on:
    non-tropical project; missing/non-dir source package; missing work root or a work root under the
    live forecast root; empty context stamp; an EXPLICIT ``db_path`` outside the work root or equal to
    the live/default DB. Deeper temp-DB reuse / pre-existing-DB checks are delegated to Phase 11 (its
    ``TempDbRehearsalError`` is mapped to a controlled refusal here).

    Then runs the Phase 11 rehearsal. If the rehearsal does not pass, returns a successful operator-run
    result with ``status='not_ready'`` and no approved artifacts. If it passes, loads the nested Phase
    10 readiness report and Phase 9 DB-mode report, validates the DB-backed context/analysis/chain
    artifacts (existence, work-root containment, live-root refusal, DB-mode semantics, chain match,
    Phase 8 explicit resolution), and writes a deterministic manifest naming the approved artifacts and
    the evidence chain. ``decision`` is ``approved_for_guarded_db_context_analysis_use``. Any
    structural/provenance inconsistency after a passed rehearsal is a controlled refusal (fail closed).
    """
    # --- Lightweight preflight (fail closed before any output). -----------------------------------
    if project_key != SUPPORTED_PROJECT_KEY:
        raise GuardedDbOperatorRunError(
            f"unsupported project_key {project_key!r}; only {SUPPORTED_PROJECT_KEY!r} is supported "
            "in Phase 12 (multi-project generalization is deferred)"
        )
    if not source_package:
        raise GuardedDbOperatorRunError("source_package is required for a guarded operator run")
    source_package = Path(source_package)
    if not source_package.exists() or not source_package.is_dir():
        raise GuardedDbOperatorRunError(
            f"source_package not found or not a directory: {source_package}"
        )
    if not work_root:
        raise GuardedDbOperatorRunError("work_root is required (explicit; no implicit output root)")
    work_root = Path(work_root)
    if _is_under(work_root, _LIVE_ROOT):
        raise GuardedDbOperatorRunError(
            f"work_root is at/under the live forecast root (refused): {work_root}"
        )
    if not context_stamp:
        raise GuardedDbOperatorRunError("context_stamp is required (explicit; no latest-glob)")
    if db_path is not None:
        db_path = Path(db_path)
        if not _is_under(db_path, work_root):
            raise GuardedDbOperatorRunError(
                f"db_path must be under work_root (refused): {db_path} not under {work_root}"
            )
        _refuse_if_live_db(db_path)

    # --- Phase 11 rehearsal (reused, never reimplemented). ----------------------------------------
    try:
        rehearsal = run_temp_db_readiness_rehearsal(
            source_package=source_package,
            work_root=work_root,
            context_stamp=context_stamp,
            db_path=db_path,
            project_key=project_key,
        )
    except TempDbRehearsalError as exc:
        raise GuardedDbOperatorRunError(f"temp-DB readiness rehearsal refused: {exc}") from exc

    rehearsal_report_path = str(rehearsal["report_path"])
    data_root = str(rehearsal["data_root"])

    # --- Not-ready evidence: a successful operator-run outcome, not a refusal. --------------------
    if rehearsal.get("status") != "passed":
        report = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "project_key": project_key,
            "status": "not_ready",
            "decision": DECISION_NOT_READY,
            "source_package": str(source_package),
            "data_root": data_root,
            "work_root": str(work_root),
            "context_stamp": context_stamp,
            "evidence": {
                "phase11_rehearsal_report": rehearsal_report_path,
                "phase11_decision": rehearsal.get("decision"),
            },
            "safety": {
                "production_defaults_changed": False,
                "live_db_written": False,
                "live_root_written": False,
                "final_integrated_csv_generated": False,
            },
        }
        report_path = _write_json_deterministic(work_root / MANIFEST_NAME, report)
        return {**report, "report_path": str(report_path)}

    # --- Passed: validate the nested DB-backed artifacts (fail closed on any inconsistency). ------
    readiness_path = (rehearsal.get("readiness") or {}).get("report_path")
    if not readiness_path:
        raise GuardedDbOperatorRunError(
            "rehearsal passed but the Phase 10 readiness report path is missing"
        )
    phase10 = _load_json(Path(readiness_path), what="Phase 10 readiness report")
    if phase10.get("decision") != READINESS_DECISION_READY:
        raise GuardedDbOperatorRunError(
            "Phase 10 readiness report is not ready after a passed rehearsal "
            f"(decision={phase10.get('decision')!r}); broken evidence chain"
        )

    db_report_path = (phase10.get("workflow") or {}).get("db_report")
    if not db_report_path:
        raise GuardedDbOperatorRunError(
            "Phase 10 readiness report has no Phase 9 DB-mode report path (broken evidence chain)"
        )
    phase9 = _load_json(Path(db_report_path), what="Phase 9 DB-mode report")

    # DB-mode semantics: only certify a genuinely DB-backed run.
    if "mode" in phase9 and phase9.get("mode") != "db":
        raise GuardedDbOperatorRunError(
            f"Phase 9 report is not a DB-mode report (mode={phase9.get('mode')!r})"
        )
    if "db_backed" in phase9 and phase9.get("db_backed") is not True:
        raise GuardedDbOperatorRunError(
            f"Phase 9 report is not db_backed (db_backed={phase9.get('db_backed')!r})"
        )

    context_package = _validated_artifact(
        raw_path=phase9.get("context_package"),
        work_root=work_root,
        what="DB-backed context package",
    )
    analysis_package = _validated_artifact(
        raw_path=phase9.get("analysis_package"),
        work_root=work_root,
        what="DB-backed analysis package",
    )
    chain_manifest = _validated_artifact(
        raw_path=phase9.get("chain_manifest"),
        work_root=work_root,
        what="DB-backed package-chain manifest",
    )

    # Phase 8: the chain manifest must resolve to the SAME context/analysis package paths.
    try:
        chain = read_package_chain_manifest(chain_manifest)
    except PackageResolutionError as exc:
        raise GuardedDbOperatorRunError(
            f"DB-backed package-chain manifest is invalid: {exc}"
        ) from exc
    chain_ctx = chain.packages.get("context")
    chain_ana = chain.packages.get("analysis")
    if chain_ctx is None or not _same_path(chain_ctx.package_path, context_package):
        raise GuardedDbOperatorRunError(
            "chain manifest context package does not match the DB-mode report context package"
        )
    if chain_ana is None or not _same_path(chain_ana.package_path, analysis_package):
        raise GuardedDbOperatorRunError(
            "chain manifest analysis package does not match the DB-mode report analysis package"
        )

    # Phase 8: explicit, fail-closed structural resolution of both approved packages.
    try:
        resolve_explicit_package(
            package_kind="context", package_path=context_package, project_key=project_key
        )
        resolve_explicit_package(
            package_kind="analysis", package_path=analysis_package, project_key=project_key
        )
    except PackageResolutionError as exc:
        raise GuardedDbOperatorRunError(
            f"approved DB-backed package failed explicit resolution: {exc}"
        ) from exc

    db_block = rehearsal.get("db") or {}
    required_tables = (rehearsal.get("projection") or {}).get("required_tables") or {}
    source_domain_counts = {
        t: int((required_tables.get(t) or {}).get("rows", 0)) for t in REQUIRED_SOURCE_DOMAIN_TABLES
    }

    report = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "project_key": project_key,
        "status": "ready",
        "decision": DECISION_APPROVED,
        "source_package": str(source_package),
        "data_root": data_root,
        "work_root": str(work_root),
        "context_stamp": context_stamp,
        "temp_db": {
            "path": str(db_block.get("path")),
            "schema_version": int(db_block.get("schema_version", REQUIRED_SCHEMA_VERSION)),
        },
        "evidence": {
            "phase11_rehearsal_report": rehearsal_report_path,
            "phase10_readiness_report": str(readiness_path),
            "phase9_db_report": str(db_report_path),
            "db_chain_manifest": str(chain_manifest),
        },
        "approved_artifacts": {
            "context_package": str(context_package),
            "analysis_package": str(analysis_package),
            "chain_manifest": str(chain_manifest),
        },
        "source_domain_counts": source_domain_counts,
        # Grounded in this controlled run's preflight + explicit-path checks (NOT a global FS audit):
        # work root verified outside the live root, temp DB refuses the live DB, no CSV generated.
        "safety": {
            "production_defaults_changed": False,
            "live_db_written": False,
            "live_root_written": False,
            "final_integrated_csv_generated": False,
        },
    }
    report_path = _write_json_deterministic(work_root / MANIFEST_NAME, report)
    return {**report, "report_path": str(report_path)}
