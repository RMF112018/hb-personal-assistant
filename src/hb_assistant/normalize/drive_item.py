"""Normalized DriveItem (OneDrive/SharePoint file) metadata model."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DriveItem(BaseModel):
    id: str
    name: Optional[str] = None
    size: Optional[int] = None
    web_url: Optional[str] = None
    is_file: bool = False
    is_folder: bool = False
    parent_reference: Optional[dict] = None
    last_modified: Optional[datetime] = None
    e_tag: Optional[str] = None
    c_tag: Optional[str] = None
    source_record_id: Optional[int] = None
    source_links: list = []
    cached_path: Optional[str] = None  # local cache after controlled download
    download_status: Optional[str] = None  # pending, success, skipped, error
