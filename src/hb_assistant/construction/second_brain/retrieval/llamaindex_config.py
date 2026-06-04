"""Phase 09 Prompt 13 — optional LlamaIndex dependency + config/status surface (read-only).

A deterministic, **read-only**, **lazy-import** status probe for the optional LlamaIndex retrieval
layer. It reports whether the optional `llama-index-core` SDK is installed (without importing it),
resolves and validates the metadata-only retrieval config (a YAML seed validated against a JSON
contract), computes a stable `config_hash`, and checks schema readiness (the V38
`second_brain_retrieval_llamaindex_config_snapshots` substrate). It builds **no** embeddings / vector
index and performs **no** semantic retrieval — those land in later Phase 09 prompts.

The SDK is an optional extra (`pip install -e ".[retrieval]"`); the base install, migrations, and the
full test suite all run with it **absent** (local-first default), so SDK-absent is the expected state
and is reported, not failed. Fail-closed on a missing/invalid contract or seed (`LlamaIndexConfigError`).
The probe opens the database **read-only** (`?mode=ro`) and never writes; outputs are labels / counts /
booleans / hashes only — no raw content, prompts, responses, tokens, URLs, secrets, or paths.

Public entry points:
  load_llamaindex_config_contract() -> dict
  load_llamaindex_config_seed() -> dict
  build_llamaindex_config_status(db_path=None) -> dict
CLI surface: hb-assistant second-brain retrieval llamaindex status --json
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

from ..contracts import load_phase_09_contract

_SEED_RELATIVE = Path("resources") / "config" / "phase_09_llamaindex_config.seed.yaml"
SEED_ENV_VAR = "HB_SECOND_BRAIN_LLAMAINDEX_CONFIG"
_SNAPSHOT_TABLE = "second_brain_retrieval_llamaindex_config_snapshots"
_SDK_PACKAGE = "llama-index-core"

# Config fields hashed into config_hash (stable, sorted) — the resolved, metadata-only shape.
_CONFIG_FIELDS = (
    "version",
    "embedding_provider",
    "embedding_model_label",
    "index_kind",
    "vector_store_kind",
    "chunk_size",
    "chunk_overlap",
    "persist_dir_label",
)


class LlamaIndexConfigError(RuntimeError):
    """Raised when the LlamaIndex config contract/seed cannot be loaded (fail-closed)."""


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


def _llama_index_available() -> bool:
    """Probe for the optional SDK without importing it (import-free)."""
    try:
        return importlib.util.find_spec("llama_index") is not None
    except (ImportError, ValueError):
        return False


def _llama_index_version() -> str | None:
    try:
        return importlib.metadata.version(_SDK_PACKAGE)
    except Exception:
        return None


def load_llamaindex_config_contract() -> dict[str, Any]:
    """Load the LlamaIndex config contract (fail-closed if missing/invalid)."""
    contract = load_phase_09_contract("llamaindex_config_contract")
    if not isinstance(contract, dict) or "required_fields" not in contract:
        raise LlamaIndexConfigError(
            "phase 09 llamaindex config contract not found or missing required_fields"
        )
    return contract


def load_llamaindex_config_seed() -> dict[str, Any]:
    """Load the resolved LlamaIndex config seed (fail-closed if missing/invalid)."""
    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    env_value = os.environ.get(SEED_ENV_VAR)
    if env_value:
        candidate = Path(env_value).expanduser()
    if not candidate.exists():
        raise LlamaIndexConfigError(f"llamaindex config seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "embedding_provider" not in data:
        raise LlamaIndexConfigError(f"{candidate} must define the llamaindex config")
    return data


def _validate_config(config: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    """Return a list of config violations (empty => valid) against the contract."""
    violations: list[str] = []
    for field in contract.get("required_fields", []):
        if config.get(field) in (None, ""):
            violations.append(f"missing_required_field:{field}")
    provider = config.get("embedding_provider")
    allowed_providers = contract.get("allowed_embedding_providers", [])
    deferred = contract.get("deferred_embedding_providers", [])
    if provider is not None and provider not in allowed_providers:
        violations.append(f"embedding_provider_not_allowed:{provider}")
    if provider in deferred:
        violations.append(f"embedding_provider_deferred:{provider}")
    index_kind = config.get("index_kind")
    if index_kind is not None and index_kind not in contract.get("allowed_index_kinds", []):
        violations.append(f"index_kind_not_allowed:{index_kind}")
    vstore = config.get("vector_store_kind")
    if vstore is not None and vstore not in contract.get("allowed_vector_store_kinds", []):
        violations.append(f"vector_store_kind_not_allowed:{vstore}")
    return violations


def _config_hash(config: dict[str, Any]) -> str:
    normalized = {k: config.get(k) for k in _CONFIG_FIELDS}
    return hashlib.sha256(
        json.dumps(normalized, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _open_ro(db_path: str | None) -> sqlite3.Connection | None:
    resolved = db_path or str(PathPolicy().get_db_path())
    try:
        return sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return None


def build_llamaindex_config_status(db_path: str | None = None) -> dict[str, Any]:
    """Build the read-only LlamaIndex dependency + config status report (fail-closed)."""
    contract = load_llamaindex_config_contract()
    seed = load_llamaindex_config_seed()

    violations = _validate_config(seed, contract)
    config_valid = not violations
    config_hash = _config_hash(seed)

    sdk_available = _llama_index_available()
    sdk_version = _llama_index_version() if sdk_available else None

    conn = _open_ro(db_path)
    schema_version = 0
    snapshot_table_present = False
    snapshot_row_count: int | None = None
    if conn is not None:
        try:
            row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
            schema_version = int(row[0]) if row and row[0] is not None else 0
            snapshot_table_present = (
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (_SNAPSHOT_TABLE,),
                ).fetchone()
                is not None
            )
            if snapshot_table_present:
                snapshot_row_count = int(
                    conn.execute(f"SELECT COUNT(*) FROM {_SNAPSHOT_TABLE}").fetchone()[0]
                )
        except sqlite3.OperationalError:
            pass
        finally:
            conn.close()

    schema_ready = schema_version >= 38 and snapshot_table_present
    ready_to_index = sdk_available and config_valid and schema_ready

    blockers: list[str] = []
    if not sdk_available:
        blockers.append("llama_index_not_installed")
    if not config_valid:
        blockers.append("config_invalid")
    if not schema_ready:
        blockers.append("schema_not_ready")

    return {
        "command": "second-brain retrieval llamaindex status",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "sdk": {
            "package": _SDK_PACKAGE,
            "available": sdk_available,
            "version": sdk_version,
            "install_hint": 'pip install -e ".[retrieval]"',
        },
        "config": {
            "version": seed.get("version"),
            "embedding_provider": seed.get("embedding_provider"),
            "embedding_model_label": seed.get("embedding_model_label"),
            "index_kind": seed.get("index_kind"),
            "vector_store_kind": seed.get("vector_store_kind"),
            "chunk_size": seed.get("chunk_size"),
            "chunk_overlap": seed.get("chunk_overlap"),
            "persist_dir_label": seed.get("persist_dir_label"),
            "config_hash": config_hash,
        },
        "config_valid": config_valid,
        "config_violations": violations,
        "contract_version": contract.get("version"),
        "deferred_embedding_providers": contract.get("deferred_embedding_providers", []),
        "schema_version": schema_version,
        "schema_version_expected": LATEST_SCHEMA_VERSION,
        "schema_ready": schema_ready,
        "snapshot_table_present": snapshot_table_present,
        "snapshot_row_count": snapshot_row_count,
        "ready_to_index": ready_to_index,
        "blockers": blockers,
        "policy_loaded": True,
        "read_only": True,
    }
