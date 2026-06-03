"""Phase 08D Prompt 02 — MCP contract + seed loading and posture.

Proves the ten registered Phase 08D JSON contracts load via the contract loader and expose
contract_name + version; that the contract files are dual-written into both resource trees
(matching the 08C precedent); and that the seven YAML seeds parse and carry the expected
fail-closed posture (all allow_* false, metadata-only receipts, stdio-only fail-closed
server policy pinned to schema V37). Declarative only — no server or dispatch is exercised.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from hb_assistant.construction.second_brain.contracts import (
    PHASE_08D_CONTRACT_FILES,
    load_all_phase_08d_contracts,
    load_phase_08d_contract,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_JSON = _REPO_ROOT / "src" / "hb_assistant" / "resources" / "json"
_ROOT_JSON = _REPO_ROOT / "resources" / "json"
_SEED_DIR = _REPO_ROOT / "resources" / "config"

_SEED_FILES = [
    "phase_08d_mcp_server_policy.seed.yaml",
    "phase_08d_mcp_allowed_tools.seed.yaml",
    "phase_08d_mcp_denied_tools.seed.yaml",
    "phase_08d_mcp_permission_policy.seed.yaml",
    "phase_08d_mcp_prompts.seed.yaml",
    "phase_08d_mcp_receipt_policy.seed.yaml",
    "phase_08d_mcp_resources.seed.yaml",
]


def test_all_08d_contracts_load_with_name_and_version() -> None:
    contracts = load_all_phase_08d_contracts()
    assert set(contracts) == set(PHASE_08D_CONTRACT_FILES)
    assert len(contracts) == 10
    for name, contract in contracts.items():
        assert contract, f"contract {name} loaded empty"
        assert contract.get("contract_name"), f"{name} missing contract_name"
        assert contract.get("version"), f"{name} missing version"


def test_08d_contracts_dual_written_into_both_resource_trees() -> None:
    for filename in PHASE_08D_CONTRACT_FILES.values():
        assert (_SRC_JSON / filename).exists(), f"missing src-tree contract {filename}"
        assert (_ROOT_JSON / filename).exists(), f"missing repo-root contract {filename}"
    # The Claude Desktop config-preview schema ships alongside (used from Prompt 09).
    assert (_SRC_JSON / "claude_desktop_config_preview.schema.json").exists()
    assert (_ROOT_JSON / "claude_desktop_config_preview.schema.json").exists()


def test_unknown_08d_contract_name_raises() -> None:
    try:
        load_phase_08d_contract("does_not_exist")
    except KeyError:
        return
    raise AssertionError("expected KeyError for unknown 08D contract name")


def test_08d_seeds_parse_and_carry_fail_closed_posture() -> None:
    for seed in _SEED_FILES:
        path = _SEED_DIR / seed
        assert path.exists(), f"missing seed {seed}"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict) and data, f"seed {seed} did not parse to a dict"
        assert data.get("phase") == "08D"

    permission = yaml.safe_load((_SEED_DIR / "phase_08d_mcp_permission_policy.seed.yaml").read_text())
    assert permission["local_only"] is True
    for flag in (
        "allow_external_writeback",
        "allow_direct_graph_api",
        "allow_direct_procore_api",
        "allow_email_send",
        "allow_calendar_update",
        "allow_arbitrary_sql",
        "allow_raw_store_access",
        "allow_final_financial_determination",
    ):
        assert permission[flag] is False, f"{flag} must be false"

    receipt = yaml.safe_load((_SEED_DIR / "phase_08d_mcp_receipt_policy.seed.yaml").read_text())
    assert receipt["metadata_only"] is True
    for flag in (
        "persist_raw_prompt",
        "persist_raw_response",
        "persist_raw_source_content",
        "persist_tokens_or_secrets",
        "persist_signed_or_download_urls",
    ):
        assert receipt[flag] is False, f"{flag} must be false"

    server = yaml.safe_load((_SEED_DIR / "phase_08d_mcp_server_policy.seed.yaml").read_text())
    assert server["transport"]["allowed"] == ["stdio"]
    for denied in ("http", "sse", "websocket", "tcp", "remote"):
        assert denied in server["transport"]["denied"]
    assert server["startup"]["fail_closed"] is True
    assert server["startup"]["require_schema_version"] == 37
