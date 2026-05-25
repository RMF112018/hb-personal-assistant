"""Normalized Attachment metadata model (metadata-first per 06 spec)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class Attachment(BaseModel):
    id: str
    parent_source_record_id: int  # links to email or calendar_event source_record
    name: Optional[str] = None
    content_type: Optional[str] = None
    size: Optional[int] = None
    is_inline: bool = False
    web_link: Optional[str] = None  # if referenceAttachment
    source_record_id: Optional[int] = None
    source_links: list = []
