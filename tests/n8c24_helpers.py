"""Shared fixtures for N8C-24 client-output-workspace tests (not a test module)."""

from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path
from typing import Any

from hb_assistant.nas_mcp.config import NasMcpConfig, NasObsidianConfig, RootSpec
from hb_assistant.store.migrator import SQLiteMigrator

OUTPUT_FOLDERS = ("00 Pending", "01 Final", "90 Archive", "99 Receipts", "99 Manifests")


def make_env(tmp_path: Path) -> dict[str, Any]:
    db = str(tmp_path / "n8c24.db")
    SQLiteMigrator(db_path=db).apply()
    out = tmp_path / "outputs"
    for f in OUTPUT_FOLDERS:
        (out / f).mkdir(parents=True, exist_ok=True)
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    cfg = NasMcpConfig(
        db_path=Path(db), audit_dir=tmp_path / "audit",
        roots={"vault": RootSpec("vault", vault, "read_write"),
               "outputs": RootSpec("outputs", out, "read_write")},
        obsidian=NasObsidianConfig(vault_root=vault, backup_dir=tmp_path / "bk", support_dir=tmp_path / "sup"),
    )
    return {"db": db, "outputs": out, "vault": vault, "config": cfg}


def good_zip_b64(members: dict[str, str] | None = None) -> str:
    members = members or {"a.txt": "hello", "sub/b.txt": "world"}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def zip_b64_with_member(name: str) -> str:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(name, "x")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def stage_and_commit(repo: Any, *, title: str = "Doc", file_type: str = "md",
                     content_mode: str = "markdown_text", content: str = "# hi\nbody",
                     destination_state: str = "final") -> dict[str, Any]:
    s = repo.stage_output_file({"title": title, "file_type": file_type, "content_mode": content_mode,
                                "content_text": content, "destination_state": destination_state,
                                "source_client": "chatgpt", "source_session_id": "SESSION-1"})
    r = repo.commit_output_file(output_id=s["output_id"], operator_approval_id=s["operator_approval_id"],
                                idempotency_key=s["idempotency_key"])
    return {"stage": s, "commit": r}
