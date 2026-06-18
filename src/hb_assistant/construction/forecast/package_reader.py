"""Parse a single forecast package directory (read-only, plain JSON).

Reads ``manifest.json`` (authoritative; see the CFR context/analysis/mapping
generators), plus optional ``input_inventory.json`` and ``validation_report.json``.
Extraction is defensive: missing keys degrade into ``warnings`` rather than raising,
so shape drift across package types never crashes the projection.

Authoritative manifest shape (from generate_forecast_context_package.py):
    package_name, generated_stamp, project{name, project_key, job, package_period},
    output_files[{path, row_count, sha256}], source_files[{label, path, sha256}],
    validation_status{gate: bool}, conclusion
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()


# Ordered (token, package_type) inference; crosswalk_v2 must precede analysis.
_TYPE_TOKENS: list[tuple[str, str]] = [
    ("crosswalk_v2", "crosswalk_v2"),
    ("forecast_context_package_", "context"),
    ("forecast_analysis_package_", "analysis"),
    ("mapping_discrepancy_workpaper_", "mapping_workpaper"),
    ("forecast_accuracy_next_package_", "intelligence"),
    ("forecast_intelligence_package_", "intelligence"),
    ("schedule_integrated_forecast_package_", "schedule_integrated"),
    ("forecast_monthly_package_", "monthly"),
    ("forecast_probability_package_", "probability"),
    ("forecast_history_informed_package_", "history_informed"),
    ("forecast_cost_frequency_package_", "cost_frequency"),
    ("forecast_comprehensive_package_", "comprehensive"),
    ("staffing_json_package_", "staffing_plan"),
]


def infer_package_type(package_name: str) -> str:
    """Infer a package_type token from the package directory name."""
    for token, ptype in _TYPE_TOKENS:
        if token in package_name:
            return ptype
    return "unknown"


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _gate_status(value: Any) -> tuple[str, str | None]:
    """Normalize a validation_status entry into (status, detail_json | None)."""
    if isinstance(value, bool):
        return ("pass" if value else "fail", None)
    if isinstance(value, dict):
        passed = value.get("passed")
        status = (
            ("pass" if passed else "fail")
            if isinstance(passed, bool)
            else str(value.get("status", "unknown"))
        )
        return (status, json.dumps(value, default=str))
    if value in ("pass", "fail", "warn"):
        return (str(value), None)
    return ("unknown", json.dumps(value, default=str))


def read_package(package_dir: Path, *, package_type: str | None = None) -> dict[str, Any]:
    """Parse one package directory into a lineage record.

    ``package_type`` (when known from the run-state) overrides name inference.
    Returns a dict with manifest fields, ``sources`` (for forecast_source_ingestions),
    ``validation_events`` (for forecast_validation_events), and ``warnings``.
    """
    package_dir = Path(package_dir)
    warnings: list[str] = []
    name = package_dir.name

    manifest_path = package_dir / "manifest.json"
    if not manifest_path.exists():
        return {
            "present": False,
            "package_dir": str(package_dir),
            "package_name": name,
            "package_type": package_type or infer_package_type(name),
            "warnings": [f"manifest.json not found in {package_dir}"],
            "sources": [],
            "validation_events": [],
        }

    manifest = _load_json(manifest_path)
    if not isinstance(manifest, dict):
        return {
            "present": False,
            "package_dir": str(package_dir),
            "package_name": name,
            "package_type": package_type or infer_package_type(name),
            "warnings": [f"manifest.json is not a JSON object in {package_dir}"],
            "sources": [],
            "validation_events": [],
        }

    package_name = str(manifest.get("package_name") or name)
    project = manifest.get("project") or {}
    stamp = manifest.get("generated_stamp")
    conclusion = manifest.get("conclusion")

    # --- sources (forecast_source_ingestions) from manifest.source_files ---
    sources: list[dict[str, Any]] = []
    for entry in manifest.get("source_files") or []:
        if not isinstance(entry, dict):
            continue
        src_path = str(entry.get("path") or entry.get("label") or "")
        sha = entry.get("sha256")
        if not sha:
            # NULL-sha fallback: deterministic per (package_name | source_path).
            # NEVER package-only — distinct paths must stay distinct so the
            # UNIQUE(project_key, source_package, source_sha256) constraint dedups correctly.
            sha = _hash(f"{package_name}|{src_path}")
            warnings.append(
                f"source_files entry missing sha256; derived from package|path: {src_path}"
            )
        sources.append(
            {
                "source_kind": str(entry.get("label") or "source_file"),
                "source_path": src_path,
                "source_sha256": str(sha),
                "row_count": entry.get("row_count"),
            }
        )

    # --- source_data_hashes / row_counts (forecast_package_manifests JSON cols) ---
    source_data_hashes = {s["source_path"]: s["source_sha256"] for s in sources if s["source_path"]}
    row_counts: dict[str, Any] = {}
    for entry in manifest.get("output_files") or []:
        if isinstance(entry, dict) and entry.get("row_count") is not None:
            row_counts[str(entry.get("path"))] = entry.get("row_count")

    # --- validation events (forecast_validation_events) from manifest.validation_status ---
    validation_events: list[dict[str, Any]] = []
    vstatus = manifest.get("validation_status")
    all_pass: bool | None = None
    if isinstance(vstatus, dict) and vstatus:
        statuses: list[str] = []
        for gate_name, value in vstatus.items():
            status, detail = _gate_status(value)
            statuses.append(status)
            validation_events.append(
                {"gate_name": str(gate_name), "status": status, "detail": detail}
            )
        all_pass = all(s == "pass" for s in statuses)
    else:
        warnings.append(
            "manifest.validation_status absent or empty; no validation events projected"
        )

    # --- upstream packages (best-effort, from input_inventory.json) ---
    upstream_packages: list[str] = []
    inv_path = package_dir / "input_inventory.json"
    if inv_path.exists():
        try:
            inventory = _load_json(inv_path)
            if isinstance(inventory, dict):
                used = inventory.get("source_packages_used") or inventory.get("sources") or []
                if isinstance(used, list):
                    upstream_packages = [str(u) for u in used if isinstance(u, (str, int))]
        except (ValueError, OSError) as exc:  # tolerate malformed inventory
            warnings.append(f"could not parse input_inventory.json: {exc}")

    return {
        "present": True,
        "package_dir": str(package_dir),
        "package_name": package_name,
        "package_type": package_type or infer_package_type(package_name),
        "package_stamp": stamp,
        "project_key": project.get("project_key"),
        "project_name": project.get("name"),
        "job_number": project.get("job"),
        "upstream_packages": upstream_packages,
        "source_data_hashes": source_data_hashes,
        "row_counts": row_counts,
        "validation_passed": all_pass,
        "validation_conclusion": conclusion,
        "sources": sources,
        "validation_events": validation_events,
        "warnings": warnings,
    }
