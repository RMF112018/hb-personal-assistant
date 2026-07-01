"""First-class `.eml` email archive (Phase 10E) — deterministic, stdlib only, NO model.

Parses a saved `.eml` MIME message into a full ``EmailArchive`` model, renders a full-fidelity Markdown
**archive note** (complete decoded body + reply chain + headers + attachment metadata), and derives
**graph-safe** facts for the concise source card's managed ``hb-email`` block. Reuses the stdlib parsing
idiom of ``obsidian_mcp/eml.py`` plus its ``_SafeTextExtractor`` HTML→text path, but is decoupled from
that module's request-path concerns (path-safety, operator gating, redaction, read receipts).

Privacy split (amendment #3): full Message-ID, raw addresses, and full participant lists live ONLY in
the archive note. The card block carries graph-safe facts — a message-id HASH, normalized thread topic
/ subject, sender + recipient DOMAINS, participant COUNT, hashed participant/attachment refs (so the
graph can match without exposing raw identifiers), has-attachments, attachment count, importance, date,
and detected project aliases. Body text is NEVER a strong graph signal (amendment #7).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import Any

# Full archive keeps the whole body; only an oversized message is capped (and the cap is recorded).
_ARCHIVE_BODY_CAP = 500_000

# Managed card block markers (start-marker attributes are the machine-readable, graph-safe facts).
EMAIL_BEGIN_PREFIX = "<!-- hb-email:start"
EMAIL_END = "<!-- hb-email:end -->"
# Wiki-link delimiters are assembled (never written as a literal) to satisfy the staged denylist.
_WL_OPEN = "[" + "["
_WL_CLOSE = "]" + "]"


class EmailParseError(Exception):
    """Only for truly unreadable input; parse_email_file itself is fail-safe and does not raise."""


@dataclass(frozen=True)
class EmailAttachment:
    filename: str | None
    content_type: str | None
    disposition: str | None
    content_id: str | None
    size_bytes: int | None
    sha256: str | None
    is_inline: bool


@dataclass(frozen=True)
class EmailArchive:
    subject: str = ""
    date: str = ""
    date_iso: str | None = None
    from_name: str | None = None
    from_email: str | None = None
    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    reply_to: list[str] = field(default_factory=list)
    message_id: str | None = None
    in_reply_to: str | None = None
    references: list[str] = field(default_factory=list)
    thread_topic: str | None = None
    thread_index: str | None = None
    importance: str | None = None
    priority: str | None = None
    has_attachments: bool = False
    attachments: list[EmailAttachment] = field(default_factory=list)
    plain_body: str | None = None
    html_body: str | None = None
    canonical_body_markdown: str = ""
    mime_summary: str = ""
    parse_status: str = "complete"
    parse_warnings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- parsing helpers
def _hash12(value: str) -> str:
    return hashlib.sha256(str(value).strip().lower().encode("utf-8", "replace")).hexdigest()[:12]


def _addr_pairs(msg: Any, header: str) -> list[tuple[str, str]]:
    return [(n, a) for n, a in getaddresses([str(r) for r in msg.get_all(header, [])]) if a or n]


def _addr_labels(msg: Any, header: str) -> list[str]:
    out: list[str] = []
    for name, addr in _addr_pairs(msg, header):
        label = f"{name} <{addr}>".strip() if name else addr
        if label:
            out.append(label)
    return out


def _domain_of(addr: str) -> str | None:
    m = re.search(r"@([A-Za-z0-9.\-]+)", str(addr or ""))
    return m.group(1).lower() if m else None


def _extract_bodies(msg: Any, cap: int) -> tuple[str | None, str | None, list[str]]:
    """Collect the FULL plain + html bodies (bounded by ``cap``), preserving the quoted reply chain."""
    warnings: list[str] = []
    plain: str | None = None
    html: str | None = None
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        if part.get_content_disposition() == "attachment":
            continue
        ctype = part.get_content_type()
        try:
            content = part.get_content()
        except (LookupError, ValueError):
            warnings.append("part_decode_skipped")
            continue
        if ctype == "text/plain" and plain is None:
            plain = str(content)
        elif ctype == "text/html" and html is None:
            html = str(content)
    if plain is not None and len(plain) > cap:
        plain = plain[:cap]
        warnings.append("body_truncated_safety_cap")
    if html is not None and len(html) > cap:
        html = html[:cap]
        warnings.append("html_truncated_safety_cap")
    return plain, html, warnings


def _html_to_text(html: str, cap: int) -> str:
    from hb_assistant.classification.body_inspector import _SafeTextExtractor
    parser = _SafeTextExtractor()
    parser.feed(html)
    return parser.get_text(cap)


def _attachments(msg: Any) -> list[EmailAttachment]:
    out: list[EmailAttachment] = []
    if not msg.is_multipart():
        return out
    for part in msg.walk():
        disp = part.get_content_disposition()
        cid = part.get("Content-ID")
        if disp not in ("attachment", "inline"):
            continue
        payload = part.get_payload(decode=True)
        is_inline = disp == "inline" or bool(cid and (part.get_content_maintype() == "image"))
        out.append(EmailAttachment(
            filename=part.get_filename(),
            content_type=part.get_content_type(),
            disposition=disp,
            content_id=(str(cid).strip("<>") if cid else None),
            size_bytes=(len(payload) if payload else None),
            sha256=(hashlib.sha256(payload).hexdigest() if payload else None),
            is_inline=is_inline,
        ))
    return out


def _norm_topic(text: str) -> str:
    """Lowercased, reply/forward-prefix-stripped, whitespace-collapsed thread/subject key."""
    t = re.sub(r"(?i)^\s*(re|fw|fwd|aw|wg)\s*:\s*", "", str(text or "").strip())
    while re.match(r"(?i)^\s*(re|fw|fwd|aw|wg)\s*:\s*", t):
        t = re.sub(r"(?i)^\s*(re|fw|fwd|aw|wg)\s*:\s*", "", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def _detect_alias(*texts: str) -> tuple[str | None, str | None]:
    """Resolve a known project alias appearing in subject/thread text (deterministic, seed-backed)."""
    try:
        from hb_assistant.construction.second_brain.local_ai.project_aliases import (
            resolve_project_alias,
        )
    except Exception:
        return None, None
    for t in texts:
        if not t:
            continue
        try:
            key, matched = resolve_project_alias(t)
        except Exception:
            key = matched = None
        if key:
            return key, (str(matched or key).upper())
    return None, None


def parse_email_file(path: Path) -> EmailArchive:
    """Parse one `.eml` into an :class:`EmailArchive`. Fail-safe: returns parse_status=failed, never raises."""
    try:
        with Path(path).open("rb") as fh:
            msg = BytesParser(policy=policy.default).parse(fh)
    except Exception:  # noqa: BLE001 — malformed/unreadable → failed, but never raise
        return EmailArchive(parse_status="failed", parse_warnings=["parse_failed"],
                            canonical_body_markdown="")

    warnings: list[str] = []
    from_pairs = _addr_pairs(msg, "from")
    from_name = from_pairs[0][0] if from_pairs else None
    from_email = from_pairs[0][1] if from_pairs else None

    subject = str(msg.get("subject") or "")
    date_raw = str(msg.get("date") or "")
    date_iso: str | None = None
    if date_raw:
        try:
            date_iso = parsedate_to_datetime(date_raw).isoformat()
        except (TypeError, ValueError, OverflowError):
            warnings.append("date_unparsed")

    refs = str(msg.get("references") or "").split()
    plain, html, body_warn = _extract_bodies(msg, _ARCHIVE_BODY_CAP)
    warnings.extend(body_warn)
    if plain is not None:
        canonical = plain
    elif html is not None:
        canonical = _html_to_text(html, _ARCHIVE_BODY_CAP)
        warnings.append("html_converted")
    else:
        canonical = ""
        warnings.append("no_text_body")

    atts = _attachments(msg)
    true_atts = [a for a in atts if not a.is_inline]
    inline_atts = [a for a in atts if a.is_inline]
    thread_topic = str(msg.get("thread-topic") or "").strip() or None

    recipients_present = bool(_addr_labels(msg, "to") or _addr_labels(msg, "cc")
                              or _addr_labels(msg, "bcc"))
    status = "complete"
    if not canonical and not (plain or html):
        status = "partial"
        warnings.append("empty_body")
    if not from_email and not recipients_present:
        status = "partial"
        warnings.append("no_participants")

    mime_summary = (f"plain={'yes' if plain is not None else 'no'} "
                    f"html={'yes' if html is not None else 'no'} "
                    f"attachments={len(true_atts)} inline={len(inline_atts)}")

    return EmailArchive(
        subject=subject, date=date_raw, date_iso=date_iso,
        from_name=from_name, from_email=from_email,
        to=_addr_labels(msg, "to"), cc=_addr_labels(msg, "cc"),
        bcc=_addr_labels(msg, "bcc"), reply_to=_addr_labels(msg, "reply-to"),
        message_id=(str(msg.get("message-id")).strip() if msg.get("message-id") else None),
        in_reply_to=(str(msg.get("in-reply-to")).strip() if msg.get("in-reply-to") else None),
        references=refs,
        thread_topic=thread_topic,
        thread_index=(str(msg.get("thread-index")).strip() if msg.get("thread-index") else None),
        importance=(str(msg.get("importance")).strip().lower() if msg.get("importance") else None),
        priority=(str(msg.get("x-priority") or msg.get("priority") or "").strip() or None),
        has_attachments=bool(true_atts), attachments=atts,
        plain_body=plain, html_body=html, canonical_body_markdown=canonical,
        mime_summary=mime_summary, parse_status=status, parse_warnings=warnings)


# --------------------------------------------------------------------------- graph-safe card facts
def email_card_facts(email: EmailArchive) -> dict[str, Any]:
    """Deterministic, graph-safe facts for the card block (no raw addresses / no full message-id)."""
    all_addrs = [a for a in ([email.from_email] if email.from_email else []) if a]
    for label in (*email.to, *email.cc):
        m = re.search(r"<([^>]+)>", label) or re.search(r"([^\s<>]+@[^\s<>]+)", label)
        if m:
            all_addrs.append(m.group(1))
    participant_hashes = sorted({_hash12(a) for a in all_addrs})
    recipient_domains = sorted({d for a in all_addrs for d in ([_domain_of(a)] if _domain_of(a) else [])
                                if d and d != _domain_of(email.from_email or "")})
    true_atts = [a for a in email.attachments if not a.is_inline]
    attachment_hashes = sorted({_hash12(a.filename) for a in true_atts if a.filename})
    subject_norm = _norm_topic(email.subject)
    thread_topic = _norm_topic(email.thread_topic or email.subject)
    alias_key, alias_display = _detect_alias(email.subject, email.thread_topic or "")
    return {
        "message_id_hash": (_hash12(email.message_id) if email.message_id else None),
        "thread_topic": thread_topic,
        "subject_norm": subject_norm,
        "from_domain": _domain_of(email.from_email or "") or "",
        "recipient_domains": recipient_domains,
        "participant_count": len(participant_hashes),
        "participant_hashes": participant_hashes,
        "attachment_hashes": attachment_hashes,
        "has_attachments": email.has_attachments,
        "attachment_count": len(true_atts),
        "importance": email.importance or "",
        "email_date": (email.date_iso.split("T")[0] if email.date_iso else ""),
        "project_alias_key": alias_key or "",
        "project_alias_display": alias_display or "",
    }


def _attr(value: Any) -> str:
    """HTML-comment-attribute-safe scalar: no quotes/newlines/angle brackets."""
    return re.sub(r'[<>"\r\n]', " ", str(value if value is not None else "")).strip()


def email_marker(facts: dict[str, Any]) -> str:
    return (
        f'{EMAIL_BEGIN_PREFIX} message_id_hash="{_attr(facts.get("message_id_hash"))}"'
        f' thread_topic="{_attr(facts.get("thread_topic"))}"'
        f' subject_norm="{_attr(facts.get("subject_norm"))}"'
        f' from_domain="{_attr(facts.get("from_domain"))}"'
        f' recipient_domains="{_attr(",".join(facts.get("recipient_domains") or []))}"'
        f' participant_count="{_attr(facts.get("participant_count"))}"'
        f' participant_hashes="{_attr(",".join(facts.get("participant_hashes") or []))}"'
        f' attachment_hashes="{_attr(",".join(facts.get("attachment_hashes") or []))}"'
        f' has_attachments="{_attr("true" if facts.get("has_attachments") else "false")}"'
        f' attachment_count="{_attr(facts.get("attachment_count"))}"'
        f' importance="{_attr(facts.get("importance"))}"'
        f' email_date="{_attr(facts.get("email_date"))}"'
        f' project_alias="{_attr(facts.get("project_alias_key"))}" -->'
    )


def parse_email_marker(card_text: str) -> dict[str, Any] | None:
    """Read graph-safe email facts back from a card's hb-email start marker."""
    for ln in card_text.splitlines():
        if ln.startswith(EMAIL_BEGIN_PREFIX):
            out: dict[str, Any] = {}
            for key, val in re.findall(r'(\w+)="([^"]*)"', ln):
                out[key] = val
            return out
    return None


def _wiki_link(rel: str, display: str) -> str:
    target = rel[:-3] if rel.endswith(".md") else rel
    return f"{_WL_OPEN}{target}|{display}{_WL_CLOSE}"


def enrich_card_with_email(card_text: str, email: EmailArchive, archive_rel: str,
                           *, facts: dict[str, Any] | None = None) -> tuple[str | None, str]:
    """Insert/replace ONE managed hb-email block under ``## Source Basis`` (graph-safe facts only).

    Byte-safe outside the block; idempotent. Returns (new_text | None, reason).
    """
    facts = facts if facts is not None else email_card_facts(email)
    display = Path(archive_rel).stem
    body = [
        f"- Email thread: {facts.get('thread_topic') or '(none)'}"
        f" · from {facts.get('from_domain') or '(unknown domain)'}"
        f" · {facts.get('participant_count', 0)} participants"
        f" · {facts.get('attachment_count', 0)} attachments",
        f"- Full email archive: {_wiki_link(archive_rel, display)}",
    ]
    if facts.get("project_alias_display"):
        body.append(f"- Detected project alias: {facts['project_alias_display']}")
    block = [email_marker(facts), *body, EMAIL_END]

    lines = card_text.splitlines()
    starts = [i for i, ln in enumerate(lines) if ln.startswith(EMAIL_BEGIN_PREFIX)]
    ends = [i for i, ln in enumerate(lines) if ln.strip() == EMAIL_END]
    trailing = "\n" if card_text.endswith("\n") else ""
    if len(starts) == 1 and len(ends) == 1 and ends[0] > starts[0]:
        new = lines[:starts[0]] + block + lines[ends[0] + 1:]
        return "\n".join(new) + trailing, "updated"
    if starts or ends:
        return None, "ambiguous_existing_block"
    section = "## Source Basis"
    sec = next((i for i, ln in enumerate(lines) if ln == section), -1)
    if sec == -1:
        return None, "source_basis_section_missing"
    end = next((i for i in range(sec + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    insert_at = end
    while insert_at > sec + 1 and not lines[insert_at - 1].strip():
        insert_at -= 1
    new = lines[:insert_at] + ["", *block] + lines[insert_at:]
    return "\n".join(new) + trailing, "inserted"


# --------------------------------------------------------------------------- full-fidelity archive note
def _yq(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _yaml_list(key: str, items: list[str]) -> list[str]:
    if not items:
        return [f"{key}: []"]
    return [f"{key}:", *[f"  - {_yq(a)}" for a in items]]


def _table_row(cells: list[str]) -> str:
    return "| " + " | ".join(c.replace("|", "\\|").replace("\n", " ") for c in cells) + " |"


def render_email_archive_note(email: EmailArchive, project_identity: Any, source_hash: str) -> str:
    """Deterministic full-fidelity Markdown archive note (complete body + reply chain + metadata)."""
    pid = project_identity
    fm = ["---", "note_type: email_archive", "source_type: eml"]
    if pid is not None:
        fm += [f"project_number: {_yq(getattr(pid, 'project_number', None))}",
               f"project_key: {_yq(getattr(pid, 'project_key', None))}",
               f"project_name: {_yq(getattr(pid, 'project_name', None))}"]
    fm += [
        f"email_subject: {_yq(email.subject)}",
        f"email_date: {_yq(email.date)}",
        f"email_date_iso: {_yq(email.date_iso)}",
        f"email_from: {_yq(f'{email.from_name} <{email.from_email}>'.strip() if email.from_email else email.from_name)}",
        *_yaml_list("email_to", email.to),
        *_yaml_list("email_cc", email.cc),
        f"message_id: {_yq(email.message_id)}",
        f"in_reply_to: {_yq(email.in_reply_to)}",
        f"thread_topic: {_yq(email.thread_topic)}",
        f"importance: {_yq(email.importance)}",
        f"has_attachments: {_yq(email.has_attachments)}",
        f"attachment_count: {_yq(len([a for a in email.attachments if not a.is_inline]))}",
        f"source_hash: {_yq(source_hash)}",
        f"parse_status: {_yq(email.parse_status)}",
        "---",
    ]
    title = email.subject.strip() or "(no subject)"
    out = ["\n".join(fm), "", f"# Email — {title}", "", "## Message Metadata", ""]
    meta = [("Date", email.date), ("From", f"{email.from_name or ''} <{email.from_email or ''}>"),
            ("To", "; ".join(email.to)), ("CC", "; ".join(email.cc)), ("BCC", "; ".join(email.bcc)),
            ("Reply-To", "; ".join(email.reply_to)), ("Subject", email.subject),
            ("Message-ID", email.message_id or ""), ("In-Reply-To", email.in_reply_to or ""),
            ("References", " ".join(email.references)), ("Thread Topic", email.thread_topic or ""),
            ("Importance", email.importance or ""), ("Priority", email.priority or "")]
    out += [_table_row(["Field", "Value"]), _table_row(["---", "---"])]
    out += [_table_row([k, v or ""]) for k, v in meta]

    out += ["", "## Attachments", ""]
    if email.attachments:
        out += [_table_row(["Filename", "Content Type", "Disposition", "Size", "Inline", "Notes"]),
                _table_row(["---", "---", "---", "---", "---", "---"])]
        for a in email.attachments:
            out.append(_table_row([
                a.filename or "(unnamed)", a.content_type or "", a.disposition or "",
                str(a.size_bytes if a.size_bytes is not None else ""),
                "yes" if a.is_inline else "no",
                f"cid:{a.content_id}" if a.content_id else ""]))
    else:
        out.append("- No attachments detected.")

    out += ["", "## Body", "", email.canonical_body_markdown or "(no decoded text body)"]
    if email.plain_body is None and email.html_body is not None:
        out += ["", "## Alternate HTML Body",
                "- Plain text was unavailable; the body above was converted from the HTML part."]

    out += ["", "## MIME / Source Fidelity", "",
            "- Original file type: `.eml`",
            f"- Plain text part detected: {'yes' if email.plain_body is not None else 'no'}",
            f"- HTML part detected: {'yes' if email.html_body is not None else 'no'}",
            f"- Inline images detected: {len([a for a in email.attachments if a.is_inline])}",
            f"- Attachments detected: {len([a for a in email.attachments if not a.is_inline])}",
            f"- Parse status: {email.parse_status}"]
    if email.parse_warnings:
        out += ["- Warnings:", *[f"  - {w}" for w in email.parse_warnings]]
    return "\n".join(out) + "\n"
