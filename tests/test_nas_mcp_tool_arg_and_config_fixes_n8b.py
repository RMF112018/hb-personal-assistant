"""N8B live-proof regression fixes for NAS MCP tool failures.

Three deployment/wiring bugs surfaced by the N8B live proof-slate:

* **B3** — the obsidian adapter passed ``max_files=args.get("max_files")`` (``None``
  when omitted) into vault tools declaring ``max_files: int = N``, so they raised
  ``'>=' not supported between 'int' and 'NoneType'``. The adapter now coerces an
  omitted cap to the tool's own default via ``_capint``.
* **B2** — plan tools load ``AppConfig`` (via ``PathPolicy``) from the shared NAS
  config file, which carries a top-level ``mcp:`` block. ``AppConfig`` kept
  ``extra="forbid"`` and rejected it ("AppConfig ... mcp Extra inputs are not
  permitted"). ``AppConfig`` now accepts an opaque ``mcp`` mapping.

(B1 — DB storage-guard path mismatch — is a deploy mount/config change, covered by
``deploy/nas/mcp/check-mcp-compose.sh``.)
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from hb_assistant.config.loader import load_config
from hb_assistant.nas_mcp import obsidian_adapter as adapter
from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec


def _cfg(tmp_path: Path) -> NasMcpConfig:
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    (vault / "a.md").write_text("# A\n\n- [ ] do thing\n", encoding="utf-8")
    (vault / "b.md").write_text("# B\n\nsee [[A]]\n", encoding="utf-8")
    audit = tmp_path / "audit"
    return NasMcpConfig(
        db_path=tmp_path / "db.sqlite",
        audit_dir=audit,
        roots={"vault": RootSpec("vault", vault, "read_write")},
        origin_auth_store_path=tmp_path / "tokens.json",
        override_store_path=tmp_path / "overrides.json",
        obsidian=NasObsidianConfig(
            vault_root=vault,
            backup_dir=audit / "obsidian-backups",
            support_dir=tmp_path / "support",
        ),
    )


# ----------------------------------------------------------------- B3: _capint


def test_capint_coerces_missing_and_none_to_default() -> None:
    assert adapter._capint({}, "max_files", 500) == 500
    assert adapter._capint({"max_files": None}, "max_files", 500) == 500
    assert adapter._capint({"max_files": 7}, "max_files", 500) == 7
    assert adapter._capint({"max_files": "12"}, "max_files", 500) == 12


def test_capped_tools_run_without_max_files(tmp_path: Path) -> None:
    """Every tool whose adapter call previously passed a raw None cap must now
    execute over an empty-args call instead of raising ``int >= None``."""
    cfg = _cfg(tmp_path)
    for tool in (
        "vault_map",
        "vault_summarize_folder",
        "vault_project_status_summary",
        "vault_extract_project_mentions",
        "vault_create_moc_plan",
        "vault_auto_link_plan",
        "vault_bulk_tagging_plan",
    ):
        result = adapter.dispatch_obsidian_tool(cfg, tool, {})
        assert isinstance(result, dict), f"{tool} did not return a dict"


def test_explicit_max_files_still_truncates(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    capped = adapter.dispatch_obsidian_tool(cfg, "vault_map", {"max_files": 1})
    assert capped.get("truncated") is True
    assert len(capped.get("files", [])) == 1


# ----------------------------------------------------------- B2: AppConfig(mcp)


def test_appconfig_accepts_unified_mcp_block(tmp_path: Path) -> None:
    cfg_path = tmp_path / "hb-pa-config.mcp.yml"
    cfg_path.write_text(
        textwrap.dedent(
            """
            paths:
              application_support_root: /volume2/personal-assistant/app-support
            mcp:
              actor: test
              db_path: /volume2/personal-assistant/app-support/db/hb-personal-assistant.sqlite
              roots:
                vault: {mount: /mnt/vault, mode: read_write}
            """
        ),
        encoding="utf-8",
    )
    cfg = load_config(cfg_path)
    assert isinstance(cfg.mcp, dict)
    assert cfg.mcp["actor"] == "test"
    assert "roots" in cfg.mcp
