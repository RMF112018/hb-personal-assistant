"""Shared fixtures for N8C-23 tests (not a test module)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
from hb_assistant.obsidian_mcp.vault_path_resolver import EXISTING_TOP_LEVEL_FOLDERS
from hb_assistant.store.migrator import SQLiteMigrator


def make_env(tmp_path: Path) -> dict[str, Any]:
    db = str(tmp_path / "n8c23.db")
    SQLiteMigrator(db_path=db).apply()
    vault = tmp_path / "vault"
    for f in EXISTING_TOP_LEVEL_FOLDERS:
        (vault / f).mkdir(parents=True, exist_ok=True)
    for sub in ("Work/03 Decisions", "Work/04 Actions", "Work/07 Knowledge", "Home/07 Learning",
                "99 System/Receipts", "99 System/Manifests"):
        (vault / sub).mkdir(parents=True, exist_ok=True)
    cfg = NasMcpConfig(
        db_path=Path(db), audit_dir=tmp_path / "audit",
        roots={"vault": RootSpec("vault", vault, "read_write")},
        obsidian=NasObsidianConfig(vault_root=vault, backup_dir=tmp_path / "bk", support_dir=tmp_path / "sup"),
    )
    return {"db": db, "vault": vault, "config": cfg}


DEFAULT_CANDIDATES = [
    {"artifact_type": "decision", "title": "Use staged artifact promotion for canonical memory",
     "domain": "work", "body_markdown": "Promote through staging + review.", "summary": "Staged promotion."},
    {"artifact_type": "preference", "title": "Connected clients act as drafting assistants",
     "domain": "work", "body_markdown": "Clients draft; server is authority.", "summary": "Drafting pref."},
    {"artifact_type": "open_loop", "title": "Define canonical artifact tool names",
     "domain": "work", "body_markdown": "Name the tools.", "summary": "Naming loop."},
    {"artifact_type": "workflow", "title": "Session capture review packet workflow",
     "domain": "work", "body_markdown": "capture->propose->review->promote.", "summary": "WF."},
    {"artifact_type": "architecture_note", "title": "Artifact workspace architecture",
     "domain": "work", "body_markdown": "Server is records authority.", "summary": "Arch."},
]


def staged_bundle(repo: Any, candidates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    sc = repo.stage_session_capture({
        "source_client": "chatgpt", "session_title": "Planning discussion",
        "capture_trigger": "document this session",
        "session_summary": "We agreed to use staged promotion for canonical memory.",
        "selected_excerpts": ["operator: let's use staging"], "redaction_state": "redacted"})
    return repo.stage_proposal_bundle(sc["session_id"], candidates or DEFAULT_CANDIDATES)
