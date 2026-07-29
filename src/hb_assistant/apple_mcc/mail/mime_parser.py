"""MIME parse helpers for captured .eml."""

from __future__ import annotations

import email
from email.message import Message
from email.policy import default


def parse_eml_bytes(data: bytes) -> Message:
    return email.message_from_bytes(data, policy=default)


def extract_bodies(msg: Message) -> dict[str, str | None]:
    text = None
    html = None
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain" and text is None:
                text = part.get_content()
            elif ctype == "text/html" and html is None:
                html = part.get_content()
    else:
        ctype = msg.get_content_type()
        body = msg.get_content()
        if ctype == "text/html":
            html = body
        else:
            text = body
    return {"text": text if isinstance(text, str) else None, "html": html if isinstance(html, str) else None}
