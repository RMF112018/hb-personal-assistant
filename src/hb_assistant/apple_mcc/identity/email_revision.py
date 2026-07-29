"""Email identity and revision key formulas."""

from __future__ import annotations

import hashlib
import unicodedata


def _h(prefix: bytes, *parts: bytes) -> str:
    b = prefix
    for p in parts:
        b += p
    return hashlib.sha256(b).hexdigest()


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def normalize_internet_message_id(imid: str | None) -> str:
    if not imid:
        return ""
    s = imid.strip().lower()
    if s.startswith("<") and s.endswith(">"):
        s = s[1:-1]
    return s


def account_locator_hash(account_name: str) -> str:
    return _h(b"acct_v1", account_name.encode("utf-8"))


def mailbox_locator_hash(account_hex: str, mailbox: str) -> str:
    return _h(b"mbx_v1", bytes.fromhex(account_hex), b"\0", mailbox.encode("utf-8"))


def mail_local_id_hash(account_hex: str, mailbox_hex: str, local_id: str) -> str:
    return _h(
        b"mail_local_v1",
        bytes.fromhex(account_hex),
        b"\0",
        bytes.fromhex(mailbox_hex),
        b"\0",
        local_id.encode("utf-8"),
    )


def canonical_message_key(*, internet_message_id: str | None, account_hex: str, local_id_hex: str) -> str:
    imid = normalize_internet_message_id(internet_message_id)
    if imid:
        return _h(b"csk_im_v1", imid.encode("utf-8"))
    return _h(b"csk_local_v1", bytes.fromhex(account_hex), b"\0", bytes.fromhex(local_id_hex))


def email_revision_key(canonical_message_key_hex: str, payload_hash_hex: str) -> str:
    return _h(b"rev_email_v1", bytes.fromhex(canonical_message_key_hex), b"\0", bytes.fromhex(payload_hash_hex))


def email_raw_snapshot_id(revision_key_hex: str) -> str:
    """Immutable snapshot PK — never Graph stable message id."""
    return _h(b"raw_email_snap_v1", revision_key_hex.encode("utf-8"))


def email_observation_id(
    provider: str,
    account_hex: str,
    local_id_hex: str,
    revision_hex: str,
    observed_at_utc: str,
) -> str:
    return _h(
        b"obs_email_v1",
        provider.encode("utf-8"),
        b"\0",
        bytes.fromhex(account_hex),
        b"\0",
        bytes.fromhex(local_id_hex),
        b"\0",
        bytes.fromhex(revision_hex),
        b"\0",
        observed_at_utc.encode("utf-8"),
    )


def email_payload_hash(
    *,
    subject: str | None,
    body_text: str | None,
    body_html: str | None,
    body_preview: str | None,
    to_recipients_json: str,
) -> str:
    parts = [subject or "", body_text or "", body_html or "", body_preview or "", to_recipients_json or "[]"]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
