"""Bounded live Apple MCC capture (Mac-side) for mail, calendar, and contacts.

Architecture:
  Mac live sources (read-only) → local spool → scp -O tar to NAS staging.
  Mac never opens managed NAS SQLite. NAS-local importer performs upserts.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from hb_assistant.apple_mcc.contracts.batch_envelope import BatchEnvelope
from hb_assistant.apple_mcc.contracts.spool_states import SpoolState
from hb_assistant.apple_mcc.identity.calendar_revision import (
    apple_absent_graph_event_id_hash,
    calendar_locator_hash,
    calendar_payload_hash,
    calendar_raw_snapshot_id,
    calendar_revision_key,
    event_local_id_hash,
    occurrence_key,
    source_locator_hash,
)
from hb_assistant.apple_mcc.identity.contact_revision import (
    contact_entity_id,
    contact_id_hash,
    contact_payload_hash,
    contact_raw_snapshot_id,
    contact_revision_key,
    container_locator_hash,
)
from hb_assistant.apple_mcc.identity.email_revision import (
    account_locator_hash,
    canonical_message_key,
    email_payload_hash,
    email_raw_snapshot_id,
    email_revision_key,
    mail_local_id_hash,
    mailbox_locator_hash,
)
from hb_assistant.apple_mcc.mail.mime_parser import extract_bodies, parse_eml_bytes
from hb_assistant.apple_mcc.probes.mail_account import (
    DEFAULT_MAIL_ACCOUNT_NAME,
    list_mail_accounts_via_jxa,
    resolve_mail_account,
)
from hb_assistant.apple_mcc.spool.ledger import SpoolLedger
from hb_assistant.apple_mcc.transport.ssh_jsonl import write_jsonl

APP_SUPPORT = Path.home() / "Library" / "Application Support" / "HB Personal Assistant"
DEFAULT_SPOOL = APP_SUPPORT / "spool" / "apple-mcc"
ALL_DOMAINS = ("mail", "calendar", "contacts")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        if (p / "tools" / "apple").is_dir():
            return p
    return Path.cwd()


def _ensure_eventkit_binary() -> Path:
    root = _repo_root()
    binary = root / "tools" / "apple" / "bin" / "eventkit_export"
    source = root / "tools" / "apple" / "EventKitExport" / "main.swift"
    if binary.is_file() and os.access(binary, os.X_OK):
        return binary
    if not source.is_file():
        raise FileNotFoundError(f"missing_eventkit_export_source:{source}")
    binary.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            "swiftc",
            "-O",
            "-framework",
            "EventKit",
            "-framework",
            "Foundation",
            str(source),
            "-o",
            str(binary),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 or not binary.is_file():
        raise RuntimeError(f"eventkit_compile_failed:{proc.stderr[:800]!r}")
    binary.chmod(0o755)
    return binary


def export_mail_live(
    *,
    account_name: str = DEFAULT_MAIL_ACCOUNT_NAME,
    mailbox: str = "Inbox",
    limit: int = 5,
) -> dict:
    script = _repo_root() / "tools" / "apple" / "mail_jxa" / "export_messages.js"
    if not script.is_file():
        raise FileNotFoundError(f"missing_export_script:{script}")
    proc = subprocess.run(
        ["osascript", "-l", "JavaScript", str(script), account_name, mailbox, str(limit)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"mail_jxa_failed rc={proc.returncode} err={proc.stderr[:500]!r}")
    data = json.loads(proc.stdout)
    if not data.get("ok"):
        raise RuntimeError(f"mail_jxa_not_ok:{data}")
    return data


def export_calendar_live(*, days: int = 14, limit: int = 50) -> dict:
    binary = _ensure_eventkit_binary()
    proc = subprocess.run(
        [str(binary), str(days), str(limit)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"eventkit_export_failed rc={proc.returncode} err={proc.stderr[:500]!r} out={proc.stdout[:500]!r}")
    data = json.loads(proc.stdout)
    if not data.get("ok"):
        raise RuntimeError(f"eventkit_not_ok:{data}")
    return data


def export_contacts_live(*, limit: int = 20) -> dict:
    script = _repo_root() / "tools" / "apple" / "contacts_jxa" / "export_contacts.js"
    if not script.is_file():
        raise FileNotFoundError(f"missing_contacts_export:{script}")
    proc = subprocess.run(
        ["osascript", "-l", "JavaScript", str(script), str(limit)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"contacts_jxa_failed rc={proc.returncode} err={proc.stderr[:500]!r}")
    data = json.loads(proc.stdout)
    if not data.get("ok"):
        raise RuntimeError(f"contacts_jxa_not_ok:{data}")
    return data


def _mail_payload(item: dict, *, account_name: str, mailbox: str, capture_run_id: str) -> tuple[dict, bytes]:
    raw = (item.get("source") or "").encode("utf-8", "replace")
    msg = parse_eml_bytes(raw)
    bodies = extract_bodies(msg)
    subject = item.get("subject") or msg.get("subject")
    imid = item.get("messageId") or msg.get("message-id")
    acct = account_locator_hash(account_name)
    mbx = mailbox_locator_hash(acct, mailbox)
    local = mail_local_id_hash(acct, mbx, str(item.get("id") or ""))
    csk = canonical_message_key(internet_message_id=imid, account_hex=acct, local_id_hex=local)
    ph = email_payload_hash(
        subject=subject,
        body_text=bodies.get("text"),
        body_html=bodies.get("html"),
        body_preview=None,
        to_recipients_json="[]",
    )
    rev = email_revision_key(csk, ph)
    snap = email_raw_snapshot_id(rev)
    payload = {
        "domain": "mail",
        "provider": "apple_mail",
        "account_name": account_name,
        "mailbox": mailbox,
        "source_local_id": str(item.get("id") or ""),
        "account_locator_hash": acct,
        "mailbox_locator_hash": mbx,
        "source_local_id_hash": local,
        "canonical_message_key": csk,
        "payload_hash": ph,
        "revision_key": rev,
        "raw_email_id": snap,
        "internet_message_id": imid,
        "subject": subject,
        "from_address": item.get("sender"),
        "body_text": bodies.get("text"),
        "raw_source_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_source_bytes": len(raw),
        "observed_at_utc": _utc_now(),
        "capture_run_id": capture_run_id,
        "source_quality": "apple_mail_full_mime",
        "fidelity_class": "full_mime",
        "raw_eml_relpath": f"raw/mail/{snap}.eml",
    }
    return payload, raw


def _calendar_payload(item: dict, *, capture_run_id: str) -> dict:
    src_title = str(item.get("source_title") or "unknown")
    cal_id = str(item.get("calendar_id") or "")
    ek_id = str(item.get("event_id") or "")
    start = str(item.get("start") or "")
    end = str(item.get("end") or "")
    subject = str(item.get("summary") or "")
    body = str(item.get("notes") or "") or None
    location = str(item.get("location") or "") or None
    src = source_locator_hash(src_title)
    cal = calendar_locator_hash(src, cal_id)
    local = event_local_id_hash(cal, ek_id)
    occ = occurrence_key(cal, ical_uid=None, ek_event_id=ek_id, start_utc=start)
    ph = calendar_payload_hash(
        subject=subject,
        body_text=body,
        body_html=None,
        body_preview=None,
        start_datetime_utc=start,
        end_datetime_utc=end,
        location_display=location,
    )
    rev = calendar_revision_key(occ, ph)
    snap = calendar_raw_snapshot_id(rev)
    return {
        "domain": "calendar",
        "provider": "apple_eventkit",
        "source_title": src_title,
        "calendar_title": item.get("calendar_title"),
        "calendar_id": cal_id,
        "event_id": ek_id,
        "source_locator_hash": src,
        "calendar_locator_hash": cal,
        "source_local_id_hash": local,
        "occurrence_key": occ,
        "payload_hash": ph,
        "revision_key": rev,
        "raw_calendar_event_id": snap,
        "graph_event_id_hash": apple_absent_graph_event_id_hash(local),
        "subject": subject,
        "body_text": body,
        "location_display": location,
        "start_datetime_utc": start,
        "end_datetime_utc": end,
        "all_day": bool(item.get("all_day")),
        "url": item.get("url") or None,
        "observed_at_utc": _utc_now(),
        "capture_run_id": capture_run_id,
        "source_quality": "apple_eventkit_full",
        "join_url_policy": "local_db_only",
        "raw_sidecar_json": json.dumps({"graph_id_absent": True, "has_recurrence": item.get("has_recurrence")}),
    }


def _contact_payload(item: dict, *, capture_run_id: str) -> dict:
    container = str(item.get("container") or "On My Mac")
    cn_id = str(item.get("cn_id") or "")
    contact_type = str(item.get("contact_type") or "person")
    if contact_type not in {"person", "organization", "unknown"}:
        contact_type = "person"
    structured = {
        "cn_id": cn_id,
        "first_name": item.get("first_name") or "",
        "last_name": item.get("last_name") or "",
        "organization": item.get("organization") or "",
        "contact_type": contact_type,
        "emails": item.get("emails") or [],
        "phones": item.get("phones") or [],
        "container": container,
    }
    payload_json = json.dumps(structured, sort_keys=True, separators=(",", ":"))
    cont = container_locator_hash(container)
    cid = contact_id_hash(cont, cn_id)
    ent = contact_entity_id(cont, cid)
    ph = contact_payload_hash(payload_json)
    rev = contact_revision_key(ent, ph)
    snap = contact_raw_snapshot_id(rev)
    return {
        "domain": "contacts",
        "provider": "cncontact_local",
        "container": container,
        "cn_id": cn_id,
        "container_locator_hash": cont,
        "contact_id_hash": cid,
        "contact_entity_id": ent,
        "contact_type": contact_type,
        "payload_hash": ph,
        "revision_key": rev,
        "raw_contact_payload_id": snap,
        "structured_payload_json": payload_json,
        "observed_at_utc": _utc_now(),
        "capture_run_id": capture_run_id,
        "source_quality": "cncontact_full",
    }


@dataclass
class CaptureResult:
    capture_run_id: str
    domains: list[str]
    counts: dict[str, int]
    spool_dir: str
    batch_path: str
    transport_path: str | None
    transport_ok: bool
    nas_staging_path: str | None
    redacted_summary: dict = field(default_factory=dict)


def run_capture(
    *,
    domains: list[str] | tuple[str, ...] = ALL_DOMAINS,
    account_name: str = DEFAULT_MAIL_ACCOUNT_NAME,
    mailbox: str = "Inbox",
    mail_limit: int = 5,
    calendar_days: int = 14,
    calendar_limit: int = 50,
    contacts_limit: int = 20,
    spool_root: Path | None = None,
    transport: bool = True,
    nas_host: str = "hb-nas",
    nas_port: str = "10021",
    nas_staging: str = "/volume2/personal-assistant/staging/apple-mcc/inbox",
) -> CaptureResult:
    wanted = [d for d in domains if d in ALL_DOMAINS]
    if not wanted:
        raise ValueError("no_valid_domains")

    capture_run_id = (
        f"cap_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    root = Path(spool_root or DEFAULT_SPOOL) / capture_run_id
    root.mkdir(parents=True, exist_ok=True)
    for sub in ("raw/mail", "raw/calendar", "raw/contacts"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    ledger = SpoolLedger(root / "ledger.sqlite")

    envelopes: list[BatchEnvelope] = []
    counts: dict[str, int] = {d: 0 for d in wanted}
    domain_errors: dict[str, str] = {}

    # --- mail ---
    if "mail" in wanted:
        try:
            accounts = list_mail_accounts_via_jxa()
            probe = resolve_mail_account(expected_name=account_name, accounts=accounts)
            if not probe.ok:
                raise RuntimeError(f"mail_probe:{probe.state.value}:{probe.detail}")
            exported = export_mail_live(account_name=account_name, mailbox=mailbox, limit=mail_limit)
            payloads: list[dict] = []
            for item in exported.get("items") or []:
                meta, raw = _mail_payload(
                    item, account_name=account_name, mailbox=mailbox, capture_run_id=capture_run_id
                )
                eml_path = root / meta["raw_eml_relpath"]
                eml_path.parent.mkdir(parents=True, exist_ok=True)
                eml_path.write_bytes(raw)
                payloads.append(meta)
                iid = meta["source_local_id_hash"]
                ledger.put(iid, "mail", _utc_now(), payload_path=str(eml_path))
                ledger.advance(iid, SpoolState.QUEUED, _utc_now())
            envelopes.append(
                BatchEnvelope.from_items(
                    batch_id=f"batch_mail_{capture_run_id}",
                    capture_run_id=capture_run_id,
                    domain="mail",
                    items=payloads,
                    created_utc=_utc_now(),
                )
            )
            counts["mail"] = len(payloads)
        except Exception as exc:  # noqa: BLE001
            domain_errors["mail"] = str(exc)[:500]

    # --- calendar ---
    if "calendar" in wanted:
        try:
            exported = export_calendar_live(days=calendar_days, limit=calendar_limit)
            payloads = []
            for item in exported.get("items") or []:
                meta = _calendar_payload(item, capture_run_id=capture_run_id)
                # store structured JSON sidecar (not ICS required for EventKit path)
                side = root / f"raw/calendar/{meta['raw_calendar_event_id']}.json"
                side.write_text(json.dumps(item, indent=2) + "\n", encoding="utf-8")
                meta["raw_json_relpath"] = str(side.relative_to(root))
                payloads.append(meta)
                iid = meta["source_local_id_hash"]
                ledger.put(iid, "calendar", _utc_now(), payload_path=str(side))
                ledger.advance(iid, SpoolState.QUEUED, _utc_now())
            envelopes.append(
                BatchEnvelope.from_items(
                    batch_id=f"batch_cal_{capture_run_id}",
                    capture_run_id=capture_run_id,
                    domain="calendar",
                    items=payloads,
                    created_utc=_utc_now(),
                )
            )
            counts["calendar"] = len(payloads)
        except Exception as exc:  # noqa: BLE001
            domain_errors["calendar"] = str(exc)[:500]

    # --- contacts ---
    if "contacts" in wanted:
        try:
            exported = export_contacts_live(limit=contacts_limit)
            payloads = []
            for item in exported.get("items") or []:
                meta = _contact_payload(item, capture_run_id=capture_run_id)
                side = root / f"raw/contacts/{meta['raw_contact_payload_id']}.json"
                side.write_text(meta["structured_payload_json"] + "\n", encoding="utf-8")
                meta["raw_json_relpath"] = str(side.relative_to(root))
                payloads.append(meta)
                iid = meta["contact_id_hash"]
                ledger.put(iid, "contacts", _utc_now(), payload_path=str(side))
                ledger.advance(iid, SpoolState.QUEUED, _utc_now())
            envelopes.append(
                BatchEnvelope.from_items(
                    batch_id=f"batch_contacts_{capture_run_id}",
                    capture_run_id=capture_run_id,
                    domain="contacts",
                    items=payloads,
                    created_utc=_utc_now(),
                )
            )
            counts["contacts"] = len(payloads)
        except Exception as exc:  # noqa: BLE001
            domain_errors["contacts"] = str(exc)[:500]

    if not envelopes:
        raise RuntimeError(f"all_domains_failed:{domain_errors}")

    batch_path = root / "batch.jsonl"
    write_jsonl(batch_path, envelopes)

    summary = {
        "capture_run_id": capture_run_id,
        "domains": wanted,
        "counts": counts,
        "domain_errors": domain_errors,
        "mail_account": account_name if "mail" in wanted else None,
        "subjects_redacted": True,
        "produced_utc": _utc_now(),
    }
    (root / "capture-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    transport_path = None
    transport_ok = False
    nas_path = None
    total_items = sum(counts.values())
    if transport and total_items > 0:
        archive = root / f"{capture_run_id}.tar.gz"
        subprocess.run(
            [
                "tar",
                "-czf",
                str(archive),
                "-C",
                str(root),
                "batch.jsonl",
                "raw",
                "capture-summary.json",
            ],
            check=True,
        )
        transport_path = str(archive)
        remote = f"{nas_staging.rstrip('/')}/{capture_run_id}.tar.gz"
        nas_path = remote
        subprocess.run(
            ["ssh", "-p", nas_port, "-o", "BatchMode=yes", nas_host, f"mkdir -p {nas_staging}"],
            check=False,
            capture_output=True,
        )
        proc = subprocess.run(
            [
                "scp",
                "-O",
                "-P",
                nas_port,
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=15",
                str(archive),
                f"{nas_host}:{remote}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            with archive.open("rb") as src:
                proc = subprocess.run(
                    [
                        "ssh",
                        "-p",
                        nas_port,
                        "-o",
                        "BatchMode=yes",
                        nas_host,
                        f"cat > {remote}",
                    ],
                    stdin=src,
                    capture_output=True,
                    text=True,
                    check=False,
                )
        transport_ok = proc.returncode == 0
        if not transport_ok:
            (root / "transport.err").write_text(proc.stderr or proc.stdout or "scp_failed", encoding="utf-8")
        else:
            # mark delivered in ledger for all queued items
            for row in ledger.conn.execute("SELECT item_id, state FROM spool_items"):
                if row[1] == SpoolState.QUEUED.value:
                    ledger.advance(row[0], SpoolState.TRANSPORTING, _utc_now())
                    ledger.advance(row[0], SpoolState.DELIVERED, _utc_now())

    return CaptureResult(
        capture_run_id=capture_run_id,
        domains=list(wanted),
        counts=counts,
        spool_dir=str(root),
        batch_path=str(batch_path),
        transport_path=transport_path,
        transport_ok=transport_ok,
        nas_staging_path=nas_path,
        redacted_summary=summary,
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="apple-mcc-capture")
    p.add_argument(
        "--domains",
        default="mail,calendar,contacts",
        help="Comma-separated: mail,calendar,contacts",
    )
    p.add_argument("--account", default=DEFAULT_MAIL_ACCOUNT_NAME)
    p.add_argument("--mailbox", default="Inbox")
    p.add_argument("--mail-limit", type=int, default=5)
    p.add_argument("--calendar-days", type=int, default=14)
    p.add_argument("--calendar-limit", type=int, default=50)
    p.add_argument("--contacts-limit", type=int, default=20)
    p.add_argument("--no-transport", action="store_true")
    p.add_argument("--spool-root", type=Path, default=None)
    args = p.parse_args(argv)
    domains = [d.strip() for d in args.domains.split(",") if d.strip()]
    result = run_capture(
        domains=domains,
        account_name=args.account,
        mailbox=args.mailbox,
        mail_limit=args.mail_limit,
        calendar_days=args.calendar_days,
        calendar_limit=args.calendar_limit,
        contacts_limit=args.contacts_limit,
        spool_root=args.spool_root,
        transport=not args.no_transport,
    )
    print(
        json.dumps(
            {
                "ok": True,
                **result.redacted_summary,
                "transport_ok": result.transport_ok,
                "spool_dir": result.spool_dir,
                "nas_staging_path": result.nas_staging_path,
            },
            indent=2,
        )
    )
    # fail if transport requested and failed, or any domain had zero with error
    if not args.no_transport and not result.transport_ok:
        return 2
    if any(result.counts.get(d, 0) == 0 and d in (result.redacted_summary.get("domain_errors") or {}) for d in domains):
        # partial success still ok if at least one domain produced items
        if sum(result.counts.values()) == 0:
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
