"""Bounded live Apple MCC capture run (Mac-side).

Mac live sources (read-only) → local spool → SSH JSONL/tar to NAS staging.
Mac never opens managed NAS SQLite. NAS-local importer performs upserts.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from hb_assistant.apple_mcc.contracts.batch_envelope import BatchEnvelope
from hb_assistant.apple_mcc.contracts.spool_states import SpoolState
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        if (p / "tools" / "apple" / "mail_jxa").is_dir():
            return p
    return Path.cwd()


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
        raise RuntimeError(f"jxa_export_failed rc={proc.returncode} err={proc.stderr[:500]!r}")
    data = json.loads(proc.stdout)
    if not data.get("ok"):
        raise RuntimeError(f"jxa_export_not_ok:{data}")
    return data


def _item_to_payload(item: dict, *, account_name: str, mailbox: str, capture_run_id: str) -> dict:
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
    return {
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
        "raw_eml_relpath": f"raw/{snap}.eml",
    }


@dataclass
class CaptureResult:
    capture_run_id: str
    exported: int
    spool_dir: str
    batch_path: str
    transport_path: str | None
    transport_ok: bool
    nas_staging_path: str | None
    redacted_summary: dict


def run_capture(
    *,
    account_name: str = DEFAULT_MAIL_ACCOUNT_NAME,
    mailbox: str = "Inbox",
    limit: int = 5,
    spool_root: Path | None = None,
    transport: bool = True,
    nas_host: str = "hb-nas",
    nas_port: str = "10021",
    nas_staging: str = "/volume2/personal-assistant/staging/apple-mcc/inbox",
) -> CaptureResult:
    accounts = list_mail_accounts_via_jxa()
    live_probe = resolve_mail_account(expected_name=account_name, accounts=accounts)
    if not live_probe.ok:
        raise RuntimeError(f"mail_account_probe_failed:{live_probe.state.value}:{live_probe.detail}")

    capture_run_id = (
        f"cap_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    root = Path(spool_root or DEFAULT_SPOOL) / capture_run_id
    raw_dir = root / "raw"
    root.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    ledger = SpoolLedger(root / "ledger.sqlite")

    exported = export_mail_live(account_name=account_name, mailbox=mailbox, limit=limit)
    payloads: list[dict] = []
    for item in exported.get("items") or []:
        raw = (item.get("source") or "").encode("utf-8", "replace")
        meta = _item_to_payload(
            item, account_name=account_name, mailbox=mailbox, capture_run_id=capture_run_id
        )
        eml_path = root / meta["raw_eml_relpath"]
        eml_path.parent.mkdir(parents=True, exist_ok=True)
        eml_path.write_bytes(raw)
        wire = dict(meta)
        payloads.append(wire)
        item_id = meta["source_local_id_hash"]
        ledger.put(item_id, "mail", _utc_now(), payload_path=str(eml_path))
        ledger.advance(item_id, SpoolState.QUEUED, _utc_now())

    env = BatchEnvelope.from_items(
        batch_id=f"batch_{capture_run_id}",
        capture_run_id=capture_run_id,
        domain="mail",
        items=payloads,
        created_utc=_utc_now(),
    )
    batch_path = root / "batch.jsonl"
    write_jsonl(batch_path, [env])

    summary = {
        "capture_run_id": capture_run_id,
        "account_name": account_name,
        "mailbox": mailbox,
        "exported": len(payloads),
        "mailbox_total_reported": exported.get("total"),
        "item_hashes": [p["raw_source_sha256"] for p in payloads],
        "subjects_redacted": True,
        "produced_utc": _utc_now(),
    }
    (root / "capture-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    transport_path = None
    transport_ok = False
    nas_path = None
    if transport and payloads:
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
        # ensure remote dir
        subprocess.run(
            [
                "ssh",
                "-p",
                nas_port,
                "-o",
                "BatchMode=yes",
                nas_host,
                f"mkdir -p {nas_staging}",
            ],
            check=False,
            capture_output=True,
        )
        # Synology SSH often has SFTP subsystem disabled; use legacy scp (-O) then ssh dd fallback.
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
            for p in payloads:
                ledger.advance(p["source_local_id_hash"], SpoolState.TRANSPORTING, _utc_now())
                ledger.advance(p["source_local_id_hash"], SpoolState.DELIVERED, _utc_now())

    return CaptureResult(
        capture_run_id=capture_run_id,
        exported=len(payloads),
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
    p.add_argument("--account", default=DEFAULT_MAIL_ACCOUNT_NAME)
    p.add_argument("--mailbox", default="Inbox")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--no-transport", action="store_true")
    p.add_argument("--spool-root", type=Path, default=None)
    args = p.parse_args(argv)
    result = run_capture(
        account_name=args.account,
        mailbox=args.mailbox,
        limit=args.limit,
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
    return 0 if (result.transport_ok or args.no_transport) else 2


if __name__ == "__main__":
    raise SystemExit(main())
