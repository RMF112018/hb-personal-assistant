"""NAS-local staged batch import (must run ON NAS under HB_NAS_RUNTIME=1)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tarfile
import tempfile
from pathlib import Path

from hb_assistant.apple_mcc.contracts.raw_fields import EmailObservationFields, EmailRawFields
from hb_assistant.construction.store.repositories import import_email_observation_and_revision
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


def _require_nas_runtime() -> None:
    if os.environ.get("HB_NAS_RUNTIME", "").strip() != "1":
        raise SystemExit("refusing: HB_NAS_RUNTIME=1 required for NAS import")


def _obs_id(revision_key: str, observed_at: str) -> str:
    return hashlib.sha256(f"{revision_key}|{observed_at}".encode()).hexdigest()


def import_archive(
    archive: Path,
    *,
    db_path: Path,
    apply_migrations: bool = False,
) -> dict:
    _require_nas_runtime()
    if apply_migrations:
        ver = SQLiteMigrator(db_path=str(db_path)).apply()
        if int(ver) != LATEST_SCHEMA_VERSION:
            raise RuntimeError(f"migration_tip_unexpected:{ver}")

    with tempfile.TemporaryDirectory(prefix="apple-mcc-import-") as td:
        tdir = Path(td)
        with tarfile.open(archive, "r:gz") as tf:
            tf.extractall(tdir)
        batch_path = tdir / "batch.jsonl"
        if not batch_path.is_file():
            raise FileNotFoundError("batch.jsonl missing in archive")
        lines = [ln for ln in batch_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        accepted = 0
        rejected = 0
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            conn.execute("BEGIN IMMEDIATE")
            for line in lines:
                env = json.loads(line)
                for item in env.get("items") or []:
                    try:
                        if item.get("domain") != "mail":
                            rejected += 1
                            continue
                        raw = EmailRawFields(
                            raw_email_id=item["raw_email_id"],
                            message_id_hash=item["source_local_id_hash"],
                            internet_message_id_hash=item.get("canonical_message_key"),
                            subject=item.get("subject"),
                            body_text=item.get("body_text"),
                            from_address=item.get("from_address"),
                            source_quality=item.get("source_quality") or "apple_mail_full_mime",
                            payload_hash=item["payload_hash"],
                            raw_capture_run_id=item.get("capture_run_id"),
                            raw_content_schema_version="email_raw_v1",
                            raw_sidecar_json=json.dumps(
                                {
                                    "provider": "apple_mail",
                                    "raw_source_sha256": item.get("raw_source_sha256"),
                                    "internet_message_id": item.get("internet_message_id"),
                                }
                            ),
                        )
                        observed = item.get("observed_at_utc") or ""
                        obs = EmailObservationFields(
                            observation_id=_obs_id(item["revision_key"], observed),
                            account_locator_hash=item["account_locator_hash"],
                            source_local_id_hash=item["source_local_id_hash"],
                            mailbox_locator_hash=item.get("mailbox_locator_hash"),
                            raw_source_sha256=item.get("raw_source_sha256"),
                            raw_source_bytes=item.get("raw_source_bytes"),
                            fidelity_class=item.get("fidelity_class"),
                            capture_run_id=item.get("capture_run_id"),
                        )
                        import_email_observation_and_revision(
                            conn,
                            observation_fields=obs,
                            revision_key=item["revision_key"],
                            canonical_message_key=item["canonical_message_key"],
                            payload_hash=item["payload_hash"],
                            raw_email=raw,
                            source_quality=item.get("source_quality") or "apple_mail_full_mime",
                            fidelity_class=item.get("fidelity_class"),
                            provider="apple_mail",
                            observed_at_utc=observed,
                        )
                        accepted += 1
                    except Exception:
                        rejected += 1
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    return {"accepted": accepted, "rejected": rejected, "db_path": str(db_path)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument(
        "--db",
        type=Path,
        default=Path("/volume2/personal-assistant/app-support/db/hb-personal-assistant.sqlite"),
    )
    p.add_argument("--apply-migrations", action="store_true")
    args = p.parse_args(argv)
    result = import_archive(args.archive, db_path=args.db, apply_migrations=args.apply_migrations)
    print(json.dumps({"ok": True, **result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
