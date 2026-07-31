"""NAS-local staged batch import for mail, calendar, and contacts.

Must run ON NAS (or as personal-assistant-svc via docker) with HB_NAS_RUNTIME=1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tarfile
import tempfile
from pathlib import Path

from hb_assistant.apple_mcc.contracts.raw_fields import (
    CalendarObservationFields,
    CalendarRawFields,
    ContactObservationFields,
    ContactRawFields,
    EmailObservationFields,
    EmailRawFields,
)
from hb_assistant.construction.store.repositories import (
    import_calendar_observation_and_revision,
    import_contact_observation_and_revision,
    import_email_observation_and_revision,
)
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


def _require_nas_runtime() -> None:
    if os.environ.get("HB_NAS_RUNTIME", "").strip() != "1":
        raise SystemExit("refusing: HB_NAS_RUNTIME=1 required for NAS import")


def _obs_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _resolve_source_account(item: dict, *fallback_keys: str) -> str:
    """Prefer explicit source_account; fall back to domain-native locator names."""
    for key in ("source_account",) + fallback_keys:
        val = item.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    raise ValueError(f"missing_source_account domain={item.get('domain')}")


def _resolve_source_scope(item: dict, *fallback_keys: str) -> str | None:
    for key in ("source_scope",) + fallback_keys:
        val = item.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return None


def _import_mail(conn: sqlite3.Connection, item: dict) -> None:
    source_account = _resolve_source_account(item, "account_name")
    source_scope = _resolve_source_scope(item, "mailbox")
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
                "source_account": source_account,
                "source_scope": source_scope,
            }
        ),
    )
    observed = item.get("observed_at_utc") or ""
    obs = EmailObservationFields(
        observation_id=_obs_id(item["revision_key"], observed, "mail"),
        account_locator_hash=item["account_locator_hash"],
        source_local_id_hash=item["source_local_id_hash"],
        mailbox_locator_hash=item.get("mailbox_locator_hash"),
        raw_source_sha256=item.get("raw_source_sha256"),
        raw_source_bytes=item.get("raw_source_bytes"),
        fidelity_class=item.get("fidelity_class"),
        capture_run_id=item.get("capture_run_id"),
        source_account=source_account,
        source_scope=source_scope,
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


def _import_calendar(conn: sqlite3.Connection, item: dict) -> None:
    source_account = _resolve_source_account(item, "source_title")
    source_scope = _resolve_source_scope(item, "calendar_title")
    sidecar = item.get("raw_sidecar_json")
    if isinstance(sidecar, str) and sidecar.strip():
        try:
            side_obj = json.loads(sidecar)
            if not isinstance(side_obj, dict):
                side_obj = {}
        except json.JSONDecodeError:
            side_obj = {"raw_sidecar": sidecar}
    else:
        side_obj = {}
    side_obj.setdefault("source_account", source_account)
    if source_scope is not None:
        side_obj.setdefault("source_scope", source_scope)
    raw = CalendarRawFields(
        raw_calendar_event_id=item["raw_calendar_event_id"],
        graph_event_id_hash=item.get("graph_event_id_hash") or "",
        subject=item.get("subject"),
        body_text=item.get("body_text"),
        location_display=item.get("location_display"),
        start_datetime_utc=item.get("start_datetime_utc"),
        end_datetime_utc=item.get("end_datetime_utc"),
        source_quality=item.get("source_quality") or "apple_eventkit_full",
        payload_hash=item["payload_hash"],
        raw_capture_run_id=item.get("capture_run_id"),
        raw_content_schema_version="calendar_raw_v1",
        join_url_policy=item.get("join_url_policy") or "local_db_only",
        raw_sidecar_json=json.dumps(side_obj, sort_keys=True),
    )
    observed = item.get("observed_at_utc") or ""
    obs = CalendarObservationFields(
        observation_id=_obs_id(item["revision_key"], observed, "calendar"),
        source_locator_hash=item["source_locator_hash"],
        calendar_locator_hash=item["calendar_locator_hash"],
        source_local_id_hash=item["source_local_id_hash"],
        graph_id_hash=None,
        ics_provenance="none",
        capture_run_id=item.get("capture_run_id"),
        raw_sidecar_json=json.dumps(side_obj, sort_keys=True),
        source_account=source_account,
        source_scope=source_scope,
    )
    import_calendar_observation_and_revision(
        conn,
        observation_fields=obs,
        revision_key=item["revision_key"],
        occurrence_key=item["occurrence_key"],
        payload_hash=item["payload_hash"],
        raw_calendar=raw,
        source_quality=item.get("source_quality") or "apple_eventkit_full",
        provider="apple_eventkit",
        observed_at_utc=observed,
    )


def _import_contact(conn: sqlite3.Connection, item: dict) -> None:
    observed = item.get("observed_at_utc") or ""
    source_account = _resolve_source_account(item, "container")
    source_scope = _resolve_source_scope(item)
    raw = ContactRawFields(
        raw_contact_payload_id=item["raw_contact_payload_id"],
        contact_entity_id=item["contact_entity_id"],
        structured_payload_json=item["structured_payload_json"],
        payload_hash=item["payload_hash"],
        schema_version="apple_contact_raw_v1",
        source_quality=item.get("source_quality") or "cncontact_full",
        created_utc=observed,
    )
    obs = ContactObservationFields(
        observation_id=_obs_id(item["revision_key"], observed, "contact"),
        container_locator_hash=item["container_locator_hash"],
        contact_id_hash=item["contact_id_hash"],
        capture_run_id=item.get("capture_run_id"),
        source_account=source_account,
        source_scope=source_scope,
    )
    provider = item.get("provider") or "cncontact_local"
    if provider not in {"cncontact_icloud", "cncontact_local", "cncontact_other"}:
        provider = "cncontact_local"
    import_contact_observation_and_revision(
        conn,
        observation_fields=obs,
        revision_key=item["revision_key"],
        contact_entity_id=item["contact_entity_id"],
        payload_hash=item["payload_hash"],
        raw_contact=raw,
        source_quality=item.get("source_quality") or "cncontact_full",
        provider=provider,
        observed_at_utc=observed,
        contact_type=item.get("contact_type") or "person",
    )


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
        by_domain: dict[str, int] = {"mail": 0, "calendar": 0, "contacts": 0}
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            conn.execute("BEGIN IMMEDIATE")
            for line in lines:
                env = json.loads(line)
                for item in env.get("items") or []:
                    domain = item.get("domain") or env.get("domain")
                    try:
                        if domain == "mail":
                            _import_mail(conn, item)
                            by_domain["mail"] += 1
                        elif domain == "calendar":
                            _import_calendar(conn, item)
                            by_domain["calendar"] += 1
                        elif domain == "contacts":
                            _import_contact(conn, item)
                            by_domain["contacts"] += 1
                        else:
                            rejected += 1
                            continue
                        accepted += 1
                    except Exception:
                        rejected += 1
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    return {
        "accepted": accepted,
        "rejected": rejected,
        "by_domain": by_domain,
        "db_path": str(db_path),
    }


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
