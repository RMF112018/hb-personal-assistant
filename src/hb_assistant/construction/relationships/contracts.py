"""Phase 07D Prompt 02 — cross-source relationship & meeting-prep contract loader.

Loads the machine-readable 07D contracts shipped under ``resources/json/`` and the
07D policy seeds under ``resources/config/``. These are the single source of truth
that later 07D prompts (relationship normalization, meeting-prep briefs, issue
history, risk digest, aging/exposure, Obsidian projections, 07D gates) read to stay
within the no-raw / no-writeback / review-controlled guardrails.

JSON loading mirrors the importlib -> filesystem -> empty fallback used by
``construction/document/contracts.py``. Seed loading mirrors the repo-root resolution
used by ``construction/config/loader.py`` (seeds live at ``resources/config/`` and are
not packaged under ``src``).

Read-only: no DB, no network, no raw content. Every contract/seed is identifier/enum
metadata only — it never contains raw email/document/calendar text, URLs, tokens, or
secrets.
"""

from __future__ import annotations

import json
from importlib import resources as importlib_resources
from pathlib import Path
from typing import Any

import yaml

from hb_assistant.config.path_policy import PathPolicy

_CONTRACT_PKG = "hb_assistant.resources.json"

# Logical contract name -> packaged filename. Keys match each file's stable logical
# name so downstream 07D prompts can request a contract by name.
PHASE_07D_CONTRACT_FILES: dict[str, str] = {
    "cross_source_relationship_contract": "cross_source_relationship_contract.json",
    "source_evidence_trail_contract": "source_evidence_trail_contract.json",
    "meeting_prep_brief_contract": "meeting_prep_brief_contract.json",
    "project_issue_history_contract": "project_issue_history_contract.json",
    "risk_digest_contract": "risk_digest_contract.json",
    "aging_exposure_report_contract": "aging_exposure_report_contract.json",
    "phase_07d_data_quality_gates": "phase_07d_data_quality_gates.json",
    "phase_07d_validation_matrix": "phase_07d_validation_matrix.json",
}

# Logical seed name -> repo-root-relative seed filename under resources/config/.
PHASE_07D_SEED_FILES: dict[str, str] = {
    "cross_source_relationship_policy": "cross_source_relationship_policy.seed.yaml",
    "review_required_relationship_rules": "review_required_relationship_rules.seed.yaml",
    "meeting_prep_brief_policy": "meeting_prep_brief_policy.seed.yaml",
    "risk_digest_policy": "risk_digest_policy.seed.yaml",
    "aging_exposure_thresholds": "aging_exposure_thresholds.seed.yaml",
}


def _load_json_resource(filename: str) -> dict[str, Any]:
    """Load a packaged json resource. importlib -> filesystem -> empty dict."""
    try:
        if hasattr(importlib_resources, "files"):
            text = (importlib_resources.files(_CONTRACT_PKG) / filename).read_text(encoding="utf-8")
        else:  # pragma: no cover - legacy importlib path
            text = importlib_resources.read_text(_CONTRACT_PKG, filename, encoding="utf-8")
        parsed = json.loads(text)
    except Exception:
        candidate = Path(__file__).resolve().parents[2] / "resources" / "json" / filename
        if candidate.exists():
            parsed = json.loads(candidate.read_text(encoding="utf-8"))
        else:
            return {}
    return parsed if isinstance(parsed, dict) else {}


def load_phase_07d_contract(name: str) -> dict[str, Any]:
    """Return the parsed 07D contract for ``name`` (a :data:`PHASE_07D_CONTRACT_FILES` key)."""
    if name not in PHASE_07D_CONTRACT_FILES:
        raise KeyError(f"unknown phase 07D contract: {name!r}")
    return _load_json_resource(PHASE_07D_CONTRACT_FILES[name])


def load_all_phase_07d_contracts() -> dict[str, dict[str, Any]]:
    """Return every 07D contract keyed by its logical name."""
    return {name: load_phase_07d_contract(name) for name in PHASE_07D_CONTRACT_FILES}


def load_phase_07d_seed(name: str) -> dict[str, Any]:
    """Return the parsed 07D policy seed for ``name`` (a :data:`PHASE_07D_SEED_FILES` key).

    Seeds resolve from ``resources/config/`` relative to the repo root (they are not
    packaged under ``src``), matching ``construction/config/loader.py``.
    """
    if name not in PHASE_07D_SEED_FILES:
        raise KeyError(f"unknown phase 07D seed: {name!r}")
    seed_path = (
        PathPolicy().resolve_repo_root() / "resources" / "config" / PHASE_07D_SEED_FILES[name]
    )
    if not seed_path.exists():
        return {}
    parsed = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
    return parsed if isinstance(parsed, dict) else {}


def load_all_phase_07d_seeds() -> dict[str, dict[str, Any]]:
    """Return every 07D policy seed keyed by its logical name."""
    return {name: load_phase_07d_seed(name) for name in PHASE_07D_SEED_FILES}
